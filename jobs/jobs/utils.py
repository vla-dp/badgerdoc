from typing import Any, Dict, Generator, List, Optional, Tuple, Union

import aiohttp.client_exceptions
import fastapi.encoders
from sqlalchemy.orm import Session

from jobs import db_service
from jobs.config import *
from jobs.logger import logger
from jobs.models import CombinedJob
from jobs.schemas import (
    AnnotationJobUpdateParamsInAnnotation,
    JobMode,
    JobParamsToChange,
)


async def get_files_data_from_datasets(
    datasets_data: List[int], current_tenant: str, jw_token: str
) -> Tuple[List[Dict[str, Any]], List[int]]:
    """Takes datasets tags from request_body.
    Returns list of dictionaries with data for an each file
    in datasets passed in request_body"""
    files_data: List[Dict[str, Any]] = []
    valid_dataset_tags: List[int] = []
    for dataset_id in datasets_data:
        try:
            logger.info(
                f"Sending request to the dataset manager "
                f"to get info about dataset {dataset_id}"
            )
            status, response = await fetch(
                method="GET",
                url=f"{HOST_ASSETS}/datasets/{dataset_id}/files",
                headers={
                    "X-Current-Tenant": current_tenant,
                    "Authorization": f"Bearer {jw_token}",
                },
                raise_for_status=True,
            )
            if status == 404:
                logger.error(
                    f"Failed request to the Dataset Manager: {response}"
                )
                continue
        except aiohttp.client_exceptions.ClientError as err:
            logger.error(f"Failed request to the Dataset Manager: {err}")
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Failed request to the Dataset Manager: {err}",
            )

        valid_dataset_tags.append(dataset_id)
        files_data.extend(response)

    return files_data, valid_dataset_tags


async def get_files_data_from_separate_files(
    separate_files_ids: List[int], current_tenant: str, jw_token: str
) -> Union[Tuple[List[Any], List[int]]]:
    """Takes ids of files from request body.
    Returns list of dictionaries with data for an each file
    with ids passed in request_body"""
    splatted_separate_files_ids = list(split_list(separate_files_ids, 100))
    all_files_data = []
    for batch in splatted_separate_files_ids:
        elements_for_page_in_dataset_manager = 100
        try:
            params = {
                "pagination": {
                    "page_num": len(separate_files_ids)
                    // elements_for_page_in_dataset_manager
                    + 1,
                    "page_size": elements_for_page_in_dataset_manager,
                },
                "filters": [{"field": "id", "operator": "in", "value": batch}],
            }
            logger.info(
                "Sending request to the dataset manager "
                "to get info about files"
            )
            _, response = await fetch(
                method="POST",
                url=f"{HOST_ASSETS}/files/search",
                body=params,
                headers={
                    "X-Current-Tenant": current_tenant,
                    "Authorization": f"Bearer {jw_token}",
                },
                raise_for_status=True,
            )
        except aiohttp.client_exceptions.ClientError as err:
            logger.error(f"Failed request to the Dataset Manager: {err}")
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Failed request to the Dataset Manager: {err}",
            )

        all_files_data.extend(response["data"])

    valid_separate_files_uuids = [
        file_data["id"] for file_data in all_files_data
    ]

    return all_files_data, valid_separate_files_uuids


def split_list(list_a: List[Any], n: int) -> Generator[List[int], None, None]:
    """Splits a list passed in chunks with no more, than elements"""
    for x in range(0, len(list_a), n):
        every_chunk = list_a[x : n + x]
        yield every_chunk


def create_file_divided_pages_list(
    file_data: Dict[Any, Any], pagination_threshold: int = PAGINATION_THRESHOLD
) -> List[List[int]]:
    """Creates a list of lists with numbers of file pages"""
    page_quantity = file_data["pages"]
    pages_list = list(range(1, page_quantity + 1))
    result = list(split_list(pages_list, pagination_threshold))
    return result


def generate_file_data(
    file_data: Dict[Any, Any],
    pages: List[int],
    job_id: int,
    output_bucket: Optional[str] = None,
    batch_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Creates init args batches from files data given"""
    converted_file_data = {
        "file": f"{file_data['path']}",
        "bucket": file_data["bucket"],
        "pages": pages,
        "output_path": f"runs/{job_id}/{file_data['id']}",
    }
    if batch_id:
        converted_file_data["output_path"] += f"/{batch_id}"
    if output_bucket and output_bucket != file_data["bucket"]:
        converted_file_data.update({"output_bucket": output_bucket})
    return converted_file_data


def convert_files_data_for_inference(
    all_files_data: List[Dict[str, Any]],
    job_id: int,
    output_bucket: Optional[str] = None,
    pagination_threshold: int = PAGINATION_THRESHOLD,
) -> List[Dict[str, Any]]:
    """Creates init args from files data to pass it into
    the Inference Pipeline Manager or Annotation microservice"""
    converted_data = []
    for file_data in all_files_data:
        divided_pages_list = create_file_divided_pages_list(
            file_data, pagination_threshold
        )

        if len(divided_pages_list) == 1:
            converted_data.append(
                generate_file_data(
                    file_data,
                    divided_pages_list[0],
                    job_id,
                    output_bucket,
                )
            )
        else:
            for batch_id, pages_list_chunk in enumerate(
                divided_pages_list, start=1
            ):
                converted_data.append(
                    generate_file_data(
                        file_data,
                        pages_list_chunk,
                        job_id,
                        output_bucket,
                        batch_id=batch_id,
                    )
                )

    return converted_data


def convert_files_data_for_annotation(
    all_files_data: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Converts files data to match Annotation Microservice schema"""
    converted_data = []
    for file_data in all_files_data:
        converted_file_data = {
            "file_id": file_data["id"],
            "pages_number": file_data["pages"],
        }
        converted_data.append(converted_file_data)
    return converted_data


async def get_pipeline_instance_by_its_name(
    pipeline_name: str,
    current_tenant: str,
    jw_token: str,
    pipeline_version: Optional[str] = None,
) -> Any:
    """Gets pipeline instance by its name"""
    params = {"name": pipeline_name}
    if pipeline_version:
        params["version"] = pipeline_version

    logger.info(
        f"Sending request to the pipeline manager to get "
        f"pipeline_id by its name - {pipeline_name} "
        f"and version {pipeline_version}"
    )
    try:
        _, response = await fetch(
            method="GET",
            url=f"{HOST_PIPELINES}/pipeline",
            params=params,
            headers={
                "X-Current-Tenant": current_tenant,
                "Authorization": f"Bearer: {jw_token}",
            },
            raise_for_status=True,
        )
    except aiohttp.client_exceptions.ClientError as err:
        logger.error(f"Failed request to the Pipeline Manager: {err}")
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed request to the Pipeline Manager: {err}",
        )
    return response


async def execute_pipeline(
    pipeline_id: int,
    job_id: int,
    files_data: List[Dict[str, Any]],
    current_tenant: str,
    jw_token: str,
) -> None:
    """Executes Run in the Inference Pipeline Manager"""
    if ROOT_PATH:
        webhook = f"{JOBS_HOST}/{ROOT_PATH}/jobs"
    else:
        webhook = f"{JOBS_HOST}/jobs"

    params = {
        "job_id": job_id,
        "webhook": webhook,
    }
    logger.info(
        f"Job id = {job_id}. Sending request to the pipeline manager."
        f" Callback_URI: {webhook}"
    )
    try:
        _, response = await fetch(
            method="POST",
            url=f"{HOST_PIPELINES}/pipelines/{pipeline_id}/execute",
            headers={
                "X-Current-Tenant": current_tenant,
                "Authorization": f"Bearer: {jw_token}",
            },
            params=params,
            body=files_data,
            raise_for_status=True,
        )
    except aiohttp.client_exceptions.ClientError as err:
        logger.error(f"Failed request to the Pipeline Manager: {err}")
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed request to the Pipeline Manager: {err}",
        )
    return None


async def execute_in_annotation_microservice(
    created_job: CombinedJob,
    jw_token: str,
    current_tenant: str,
) -> None:

    """Sends specifically formatted files data to the Annotation Microservice
    and triggers tasks creation in it"""
    job_id = created_job.id

    if ROOT_PATH:
        callback_url = f"{JOBS_HOST}/{ROOT_PATH}/jobs/{job_id}"
    else:
        callback_url = f"{JOBS_HOST}/jobs/{job_id}"

    headers = {
        "X-Current-Tenant": current_tenant,
        "Authorization": f"Bearer: {jw_token}",
    }
    json = {
        "job_type": created_job.type,
        "callback_url": callback_url,
        "owners": created_job.owners,
        "annotators": created_job.annotators,
        "validators": created_job.validators,
        "files": created_job.files,
        "datasets": created_job.datasets,
        "categories": created_job.categories,
        "deadline": fastapi.encoders.jsonable_encoder(created_job.deadline),
    }
    is_optional_fields_set = (
        created_job.validation_type and created_job.is_auto_distribution
    )
    if is_optional_fields_set:
        json["validation_type"] = created_job.validation_type
        json["is_auto_distribution"] = created_job.is_auto_distribution
    logger.info(
        f"Job id = {job_id}. Sending request to annotation manager. "
        f" Callback URI is {callback_url}, headers={headers}, params sent = {json}"
    )
    # --------- request to an annotation microservice ---------- #
    try:
        _, response = await fetch(
            method="POST",
            url=f"{HOST_ANNOTATION}/jobs/{job_id}",
            headers=headers,
            body=json,
            raise_for_status=True,
        )
    except aiohttp.client_exceptions.ClientError as err:
        logger.error(f"Failed request to the Annotation Manager: {err}")
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed request to the Annotation Manager: {err}",
        )
    # ----------------------------------------------------------------- #
    return None


def delete_duplicates(
    files_data: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Delete duplicates"""
    used_file_ids = set()

    for i in range(len(files_data) - 1, -1, -1):
        if files_data[i]["id"] in used_file_ids:
            del files_data[i]
        else:
            used_file_ids.add(files_data[i]["id"])

    return files_data


def pick_params_for_annotation(
    new_job_params: JobParamsToChange,
) -> AnnotationJobUpdateParamsInAnnotation:
    picked_params = AnnotationJobUpdateParamsInAnnotation.parse_obj(
        new_job_params
    )
    return picked_params


async def start_job_in_annotation(
    job_id: int,
    current_tenant: str,
    jwt_token: str,
) -> None:
    headers = {
        "X-Current-Tenant": current_tenant,
        "Authorization": f"Bearer: {jwt_token}",
    }

    logger.info(
        f"Job id = {job_id}. Sending request to start job in annotation manager."
        f"Headers={headers}"
    )
    try:
        _, response = await fetch(
            method="POST",
            url=f"{HOST_ANNOTATION}/jobs/{job_id}/start",
            headers=headers,
            raise_for_status=True,
        )
    except aiohttp.client_exceptions.ClientError as err:
        logger.error(
            "Failed request to the Annotation Manager: {}".format(err)
        )
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Failed request to the Annotation Manager: {}".format(err),
        )


async def update_job_in_annotation(
    job_id: int,
    new_job_params_for_annotation: AnnotationJobUpdateParamsInAnnotation,
    current_tenant: str,
    jw_token: str,
) -> None:
    headers = {
        "X-Current-Tenant": current_tenant,
        "Authorization": f"Bearer: {jw_token}",
    }

    logger.info(
        f"Job id = {job_id}. Sending request to update job in annotation manager. "
        f" Headers={headers}, params sent = {new_job_params_for_annotation}"
    )
    try:
        _, response = await fetch(
            method="PATCH",
            url=f"{HOST_ANNOTATION}/jobs/{job_id}",
            headers=headers,
            body=new_job_params_for_annotation.dict(exclude_defaults=True),
            raise_for_status=True,
        )
    except aiohttp.client_exceptions.ClientError as err:
        logger.error(f"Failed request to the Annotation Manager: {err}")
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed request to the Annotation Manager: {err}",
        )


async def get_job_progress(
    job_id: int, session: Session, current_tenant: Optional[str], jw_token: str
) -> Optional[Dict[str, int]]:
    """Get progress of the job with 'job_id' from Pipelines
    or Annotation Manager depending on 'job_mode'."""
    job = db_service.get_job_in_db_by_id(session, job_id)
    if job is None:
        logger.warning(f"job with id={job_id} not present in the database.")
        return None

    url: str = ""
    if job.mode == JobMode.Automatic:
        url = f"{HOST_PIPELINES}/jobs/{job_id}/progress"
    elif job.mode == JobMode.Manual:
        url = f"{HOST_ANNOTATION}/jobs/{job_id}/progress"
    headers = {
        "X-Current-Tenant": current_tenant,
        "Authorization": f"Bearer: {jw_token}",
    }
    timeout = aiohttp.ClientTimeout(total=5)
    try:
        _, response = await fetch(
            method="GET", url=url, headers=headers, timeout=timeout
        )
    except aiohttp.client_exceptions.ClientError as err:
        logger.error(f"Failed request url = {url}, error = {err}")
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed request to the Annotation Manager: {err}",
        )

    response.update({"mode": str(job.mode)})
    return response  # type: ignore


async def fetch(
    method: str,
    url: str,
    body: Optional[Any] = None,
    headers: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> Tuple[int, Any]:
    async with aiohttp.request(
        method=method, url=url, json=body, headers=headers, **kwargs
    ) as resp:
        status_ = resp.status
        json = await resp.json()
        return status_, json

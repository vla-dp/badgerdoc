import { Category, Link } from 'api/typings';
import {
    Annotation,
    AnnotationBoundType,
    AnnotationImageToolType,
    AnnotationLinksBoundType,
    Bound,
    Point
} from 'shared';
import { getAnnotationElementId } from './use-annotation-links';

export const offsetRelative = (element: HTMLElement, top: HTMLElement | Element) => {
    let parent = element.parentElement!;
    let offset = { left: element.offsetLeft, top: element.offsetTop };

    if (!top) return offset;
    if (parent.tagName == 'body') return offset;
    if (top.parentElement === parent) return offset;
    if (top === parent) return offset;
    let parent_offset = offsetRelative(parent, top);
    offset.top += parent_offset.top;
    offset.left += parent_offset.left;
    return offset;
};

export type PointSet = {
    start: Point;
    finish: Point;
    link: Link;
    category: Category;
    type: string;
};

const getCategoryById = (id: string | number, categories: Category[] | undefined): Category => {
    return categories?.filter((cat: Category) => cat.id == id)[0] as Category;
};

const getAnnotationById = (id: string | number, annotations: Annotation[]): Annotation => {
    return annotations.find((ann: Annotation) => ann.id == id)!;
};

const getTrueBound = (elem: HTMLElement): DOMRect => {
    const box = JSON.parse(JSON.stringify(elem.getBoundingClientRect()));
    const wrapper = document.getElementsByClassName('react-pdf__Document');
    const relOffset = offsetRelative(elem, wrapper[0]);
    return {
        ...box,
        top: relOffset.top,
        left: relOffset.left
    };
};

export const getAnnotationPage = (all: Record<number, Annotation[]>, annotation: Annotation) => {
    let pageNum = (Object.keys(all) as unknown as Array<number>).forEach((key: number) => {
        if (all[key].find((ann) => ann == annotation) === annotation) return key;
    });
    return pageNum;
};

export const getPointsForLinks = (
    id: number | string,
    annType: AnnotationBoundType | AnnotationLinksBoundType | AnnotationImageToolType,
    pageNum: number,
    links: Link[],
    annotations: Annotation[],
    categories: Category[] | undefined
) => {
    let firstChildStart: DOMRect, lastChildStart: DOMRect;
    let elementStart = document.getElementById(getAnnotationElementId(pageNum, id))!;
    if (!elementStart) return [];
    if (annType == 'text') {
        firstChildStart = getTrueBound(elementStart.firstChild! as HTMLElement);
        lastChildStart = getTrueBound(elementStart.lastChild! as HTMLElement);
    }
    let boundStart = getTrueBound(elementStart);
    let boundsFinish = links
        .filter((link) => getAnnotationById(link.to, annotations))
        .map((link) => {
            const categoryName = getCategoryById(link.category_id, categories);
            const boundType = getAnnotationById(link.to, annotations).boundType;
            const elem = document.getElementById(getAnnotationElementId(link.page_num, link.to))!;
            if (boundType == 'text') {
                return {
                    bound: [
                        getTrueBound(elem.firstChild! as HTMLElement),
                        getTrueBound(elem.lastChild! as HTMLElement)
                    ],
                    category: categoryName,
                    linkType: link.type,
                    boundType: boundType,
                    link: link
                };
            }
            return {
                bound: getTrueBound(elem),
                category: categoryName,
                linkType: link.type,
                boundType: boundType,
                link: link
            };
        });

    let linkPointA: Point, linkPointB: Point;
    let points: PointSet[] = boundsFinish.map((bound) => {
        let higherBound: DOMRect | null;
        let lowerBound: DOMRect | null;
        let higherType: string | null;
        let lowerType: string | null;
        if (bound.boundType == 'text') {
            [higherBound, lowerBound, higherType, lowerType] =
                annType == 'text'
                    ? getHigherBound2(
                          [firstChildStart, lastChildStart],
                          bound.bound,
                          annType,
                          bound.boundType
                      )
                    : getHigherBound2([boundStart], bound.bound, annType, bound.boundType);
        } else {
            [higherBound, lowerBound, higherType, lowerType] =
                annType == 'text'
                    ? getHigherBound2(
                          [firstChildStart, lastChildStart],
                          [bound.bound],
                          annType,
                          bound.boundType
                      )
                    : getHigherBound2([boundStart], [bound.bound], annType, bound.boundType);
        }
        if (higherBound) {
            if (lowerType == 'text') {
                linkPointA = {
                    x: lowerBound!.left,
                    y: lowerBound!.top + lowerBound!.height / 2
                };
            } else {
                linkPointA = {
                    x: lowerBound!.left + lowerBound!.width / 2,
                    y: lowerBound!.top
                };
            }
            if (higherType == 'text') {
                linkPointB = {
                    x: higherBound.left + higherBound.width,
                    y: higherBound.top + higherBound.height / 2
                };
            } else {
                linkPointB = {
                    x: higherBound.left + higherBound.width / 2,
                    y: higherBound.top + higherBound.height
                };
            }
        } else {
            let leftBound: DOMRect;
            let rightBound: DOMRect;
            let leftType: string;
            let rightType: string;

            if (bound.boundType == 'text') {
                [leftBound, rightBound, leftType, rightType] =
                    annType == 'text'
                        ? getLeftBound2(
                              [firstChildStart, lastChildStart],
                              bound.bound,
                              annType,
                              bound.boundType
                          )
                        : getLeftBound2([boundStart], bound.bound, annType, bound.boundType);
            }
            if (annType == 'text') {
                [leftBound, rightBound, leftType, rightType] =
                    bound.boundType == 'text'
                        ? getLeftBound2(
                              [firstChildStart, lastChildStart],
                              bound.bound,
                              annType,
                              bound.boundType
                          )
                        : getLeftBound2(
                              [firstChildStart, lastChildStart],
                              [bound.bound],
                              annType,
                              bound.boundType
                          );
            } else {
                [leftBound, rightBound, leftType, rightType] = getLeftBound2(
                    [boundStart],
                    [bound.bound] as DOMRect[],
                    annType,
                    bound.boundType
                );
            }
            linkPointA = {
                x: leftBound.left + leftBound.width,
                y: leftBound.top + leftBound.height / 2
            };
            linkPointB = {
                x: rightBound.left,
                y: rightBound.top + rightBound.height / 2
            };
        }
        return {
            start: linkPointA,
            finish: linkPointB,
            link: bound.link,
            category: bound.category,
            type: bound.linkType
        } as PointSet;
    });
    return points;
};

export const getTopOffset = (bound1: Bound, bound2: Bound) => {
    if (bound1.y + bound1.height < bound2.y) {
        return bound2.y;
    }
    if (bound2.y + bound2.height < bound1.y) {
        return bound2.y + bound2.height;
    }
};

export const getHigherBound = (boundStart: DOMRect, boundFinish: DOMRect): DOMRect | null => {
    if (boundStart.top + boundStart.height < boundFinish.top) return boundStart;
    if (boundStart.top > boundFinish.top + boundFinish.height) return boundFinish;
    return null;
};

export const getHigherBound2 = (
    boundsStart: DOMRect[],
    boundsFinish: DOMRect[],
    typeStart: string,
    typeFinish: string
): [DOMRect | null, DOMRect | null, string | null, string | null] => {
    if (
        boundsStart[boundsStart.length - 1].top + boundsStart[boundsStart.length - 1].height <
        boundsFinish[0].top
    )
        return [boundsStart[boundsStart.length - 1], boundsFinish[0], typeStart, typeFinish];
    if (
        boundsStart[0].top >
        boundsFinish[boundsFinish.length - 1].top + boundsFinish[boundsFinish.length - 1].height
    )
        return [boundsFinish[boundsFinish.length - 1], boundsStart[0], typeFinish, typeStart];
    return [null, null, null, null];
};

export const getLeftBound2 = (
    boundsStart: DOMRect[],
    boundsFinish: DOMRect[],
    typeStart: string,
    typeFinish: string
): [DOMRect, DOMRect, string, string] => {
    if (
        boundsStart[boundsStart.length - 1].left + boundsStart[boundsStart.length - 1].width <
        boundsFinish[0].left
    )
        return [boundsStart[boundsStart.length - 1], boundsFinish[0], typeStart, typeFinish];
    return [boundsFinish[boundsFinish.length - 1], boundsStart[0], typeFinish, typeStart];
};

export const getLeftBound = (boundStart: DOMRect, boundFinish: DOMRect): DOMRect => {
    return boundStart.left < boundFinish.left ? boundStart : boundFinish;
};

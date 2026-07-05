import cv2
import numpy as np

def extract_manhwa_panels(img, min_pct=2, max_pct=90):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, thresh = cv2.threshold(blur, 230, 255, cv2.THRESH_BINARY)
    h, w = thresh.shape
    cv2.rectangle(thresh, (0, 0), (w-1, h-1), 0, 10)
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(thresh, 4, cv2.CV_32S)
    if num_labels < 2:
        return []
    areas = [(i, stats[i, cv2.CC_STAT_AREA]) for i in range(1, num_labels)]
    areas.sort(key=lambda x: -x[1])
    if len(areas) > 1:
        bg_label = areas[0][0]
    else:
        return []
    mask = np.where(labels == bg_label, 255, 0).astype(np.uint8)
    cv2.rectangle(mask, (0, 0), (w-1, h-1), 255, 10)
    contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    img_area = h * w
    min_area = min_pct / 100.0 * img_area
    max_area = max_pct / 100.0 * img_area
    panels = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < min_area or area > max_area:
            continue
        x, y, w, h = cv2.boundingRect(cnt)
        panels.append((x, y, w, h))
    panels.sort(key=lambda p: p[1])
    return panels

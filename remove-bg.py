"""
Kiddo POST 插畫去背工具
讀 kids.png (白底) → 輸出 kids-transparent.png (透明底)

做法：從 4 個邊角 flood fill 白色區域為透明
相比「所有白色都變透明」更安全，不會把衣服/臉上的白色部分挖掉
"""
from PIL import Image
from collections import deque


def remove_white_background(src: str, dst: str, threshold: int = 20):
    """
    從四邊 flood fill 近白色像素為透明
    threshold: 越大去得越乾淨但可能吃掉邊緣線條；越小越保守
    """
    img = Image.open(src).convert("RGBA")
    w, h = img.size
    pixels = img.load()

    # 判斷一個像素是否「接近白色」(各通道都 > 255-threshold)
    def is_near_white(rgba):
        r, g, b, a = rgba
        return r >= 255 - threshold and g >= 255 - threshold and b >= 255 - threshold

    # BFS flood fill 從所有邊緣像素開始
    visited = [[False] * w for _ in range(h)]
    queue = deque()

    # 加入四邊的起始點
    for x in range(w):
        if is_near_white(pixels[x, 0]):
            queue.append((x, 0))
        if is_near_white(pixels[x, h - 1]):
            queue.append((x, h - 1))
    for y in range(h):
        if is_near_white(pixels[0, y]):
            queue.append((0, y))
        if is_near_white(pixels[w - 1, y]):
            queue.append((w - 1, y))

    count = 0
    while queue:
        x, y = queue.popleft()
        if x < 0 or x >= w or y < 0 or y >= h:
            continue
        if visited[y][x]:
            continue
        if not is_near_white(pixels[x, y]):
            continue
        visited[y][x] = True
        # 標記為透明
        pixels[x, y] = (255, 255, 255, 0)
        count += 1
        # 擴散到 4 個方向
        queue.extend([(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)])

    img.save(dst, "PNG", optimize=True)
    print(f"✅ 完成：{dst}")
    print(f"   {count:,} 個像素被設為透明 ({count * 100 // (w * h)}%)")


if __name__ == "__main__":
    import sys
    src = sys.argv[1] if len(sys.argv) > 1 else "parent-intel-site/kids.png"
    dst = sys.argv[2] if len(sys.argv) > 2 else "parent-intel-site/kids-transparent.png"
    threshold = int(sys.argv[3]) if len(sys.argv) > 3 else 20
    remove_white_background(src, dst, threshold)

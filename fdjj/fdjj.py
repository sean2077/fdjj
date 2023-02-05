import json
import os
import typing
from pathlib import Path

import pyautogui as pg
import pynput.mouse
import typer
from rich import print

app = typer.Typer(add_completion=False)


######################################## utils ########################################


def read_json(fpath: str) -> dict:
    with open(fpath, "r") as f:
        return json.load(f)


def dump_json(d: dict, fpath: str):
    with open(fpath, "w") as f:
        json.dump(d, f, indent=4)


def pick_point(point_num: int = 1):
    print(f"按左键取 {point_num} 个点: ")
    res = []

    def on_click(x, y, button, pressed):
        if pressed:
            res.append((x, y))
            print(f"({x},{y}) ")
            if len(res) == point_num:
                return False

    with pynput.mouse.Listener(on_click=on_click) as listener:
        listener.join()

    return res


def capture_image(l: int, t: int, w: int, h: int, *, image_path):
    pg.screenshot(image_path, region=(l, t, w, h))


######################################## 标定 ########################################


LOCATION_KEYS = {
    "app_box": "小程序",
    "skill1_box": "技能1",
    "skill2_box": "技能2",
    "skill3_box": "技能3",
    "zhoushu1_point": "咒术1",
    "zhoushu2_point": "咒术2",
    "huanshen_point": "幻神",
    "zhaohuan_point": "召唤",
}


@app.command()
def calib(out_file: str = typer.Argument("config/calib.json", help="标定结果文件")):
    """标定小程序界面及相关点位"""
    calib = {}

    keys = tuple(LOCATION_KEYS.keys())
    key_idx = 0

    def pick(x, y):
        key = keys[key_idx]
        if key.endswith("_point"):
            calib[key] = (x, y)
            print(f"({x},{y}) ")
        elif key.endswith("_box"):
            if key not in calib:
                calib[key] = [None, None]
            # 仅保留最后取得两个点
            calib[key][0] = calib[key][1]
            calib[key][1] = (x, y)
            print(f"({x},{y}) ")

    def on_click(x, y, button, pressed):
        if not pressed:
            return True

        # 按中键退出
        if button == pynput.mouse.Button.middle:
            print("用户退出")
            return False

        nonlocal key_idx
        if button == pynput.mouse.Button.left:
            key_idx -= 1
            if key_idx < 0:
                key_idx = len(keys) - 1
        elif button == pynput.mouse.Button.right:
            key_idx += 1
            if key_idx >= len(keys):
                key_idx = 0

        print(f"[green]设置[/green][red]{keys[key_idx]}[/red]: ")

    def on_scroll(x, y, dx, dy):
        pick(x, y)

    print(
        """标定小程序界面及相关点位

操作说明:

取点 - 向上或向下滚动
切换 - 按左键/右键
退出 - 按中键
"""
    )
    print(f"[green]设置[/green][red]{keys[key_idx]}[/red]: ")

    with pynput.mouse.Listener(on_click=on_click, on_scroll=on_scroll) as listener:
        listener.join()

    if len(calib) != len(keys):
        print("标定点数不够，标定失败")
        return

    dump_json(calib, out_file)
    print(calib)
    print("标定成功")


######################################## 归一化 ########################################


def normalize_coords(d: dict):
    """归一化坐标"""
    app_box = d["app_box"]

    l0, t0 = app_box[0]
    r0, b0 = app_box[1]
    w, h = r0 - l0, b0 - t0

    def _cvt(item):
        if isinstance(item, typing.Sequence) and isinstance(item[0], typing.Sequence):
            return tuple(_cvt(subitem) for subitem in item)
        return (item[0] - l0) / w, (item[1] - t0) / h

    return {k: _cvt(v) for k, v in d.items()}


@app.command()
def norm(
    calib_file: Path = typer.Argument("config/calib.json", help="标定文件"),
    config_file: Path = typer.Argument("config/config.json", help="配置文件"),
):
    """根据标定文件更新归一化坐标，并更新到配置文件中"""
    calib = read_json(calib_file)
    locations = normalize_coords(calib)
    print(locations)

    config = read_json(config_file)
    config["locations"] = locations
    dump_json(config, config_file)


######################################## 截取技能图 ########################################

# 默认的技能相对位置的归一化坐标
SKILL_LOCATION_MAP = [
    (
        (0.09780775716694773, 0.6078431372549019),
        (0.2478920741989882, 0.6880570409982175),
    ),
    (
        (0.09780775716694773, 0.7361853832442068),
        (0.2478920741989882, 0.8163992869875223),
    ),
    (
        (0.09780775716694773, 0.8645276292335116),
        (0.2478920741989882, 0.9447415329768271),
    ),
]


@app.command()
def capture(
    image_root: str = typer.Option("data/skills", "-o", help="存图目录"),
    calib_file: str = typer.Option(None, "-c", help="标定文件，若不指定，则使用默认坐标"),
    app_box_str: str = typer.Option(None, "-a", help="手动指定小程序窗口坐标: l,t,r,b"),
):
    """截取技能小图"""
    if calib_file:
        calib = read_json(calib_file)
        locations = normalize_coords(calib)
        l0, t0 = calib["app_box"][0]
        r0, b0 = calib["app_box"][1]
        skill_boxes = [locations[f"skill{i+1}_box"] for i in range(3)]
    elif app_box_str:
        l0, t0, r0, b0 = tuple(map(int, app_box_str.split(",")))
        skill_boxes = list(SKILL_LOCATION_MAP)
    else:
        print("请手动标注小程序的左上和右下顶点:")
        pts = pick_point(2)
        l0, t0 = pts[0]
        r0, b0 = pts[1]
        skill_boxes = list(SKILL_LOCATION_MAP)

    print(f"app box: {l0},{t0},{r0},{b0}")

    w0 = r0 - l0
    h0 = b0 - t0

    os.makedirs(image_root, exist_ok=True)
    for i, box in enumerate(skill_boxes):
        path = os.path.join(image_root, f"_tmp{i}.png")
        l = l0 + w0 * box[0][0]
        t = t0 + h0 * box[0][1]
        w = w0 * (box[1][0] - box[0][0])
        h = h0 * (box[1][1] - box[0][1])
        capture_image(l, t, w, h, image_path=path)


######################################## 定位小程序窗口 ########################################


IMAGE_ROOT = "data"
APP_TITLE = os.path.join(IMAGE_ROOT, "app_title.png")
APP_BOTTOM = os.path.join(IMAGE_ROOT, "app_bottom.png")


def locate_app_left_top():
    """定位 app 窗口左上位置"""

    box = pg.locateOnScreen(APP_TITLE, confidence=0.7)

    # 未找到小程序界面
    if not box:
        res = input(
            """未找到小程序界面标题, 请选择:
-）手动输入小程序界面的左上顶点坐标，格式为 left,top
q) 退出
请输入:"""
        )
        if res == "q":
            exit(0)
        try:
            l, t = tuple(map(int, res.split(",")))
        except Exception:
            print("输入无效!!!")
            exit(1)
    else:
        l, t = box.left, box.top

    print(f"小程序界面左上顶点点为: {l}, {t}")
    return int(l), int(t)


def locate_app_right_bottom():
    """定位 app 窗口右下位置"""

    box = pg.locateOnScreen(APP_BOTTOM, confidence=0.7)

    # 未找到小程序界面
    if not box:
        res = input(
            """未找到小程序界面底部, 请选择:
-）手动输入小程序界面的右下顶点坐标，格式为 right,bottom
q) 退出
请输入:"""
        )
        if res == "q":
            exit(0)
        try:
            r, b = tuple(map(int, res.split(",")))
        except Exception:
            print("输入无效!!!")
            exit(1)
    else:
        r, b = box.left + box.width, box.top + box.height

    print(f"小程序界面右下顶点为: {r}, {b}")
    return int(r), int(b)


@app.command()
def locate():
    """自动定位小程序位置"""

    l0, t0 = locate_app_left_top()
    r0, b0 = locate_app_right_bottom()
    print(f"app box: {l0},{t0},{r0},{b0}")
    return l0, t0, r0, b0


def main():
    try:
        app()
    except Exception as e:
        typer.echo(e)


if __name__ == "__main__":
    main()

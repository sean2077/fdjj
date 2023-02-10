import json
import os
import random
import time
from pathlib import Path
from typing import Sequence, Tuple

import pyautogui as pg
import pynput.mouse
import typer
from rich import print

app = typer.Typer(add_completion=False)

Point = Tuple[float, float]
Box = Tuple[Point, Point]


######################################## utils ########################################


def read_json(fpath: str | Path) -> dict:
    with open(fpath, "r") as f:
        return json.load(f)


def dump_json(d: dict, fpath: str | Path):
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
    "steer_point": "转盘中心",
}


@app.command()
def calib(out_file: str = typer.Argument("config/calib.json", help="标定结果文件")):
    """标定小程序界面及相关点位"""
    d = {}

    keys = tuple(LOCATION_KEYS.keys())
    key_idx = 0

    def pick(x, y):
        key = keys[key_idx]
        if key.endswith("_point"):
            d[key] = (x, y)
            print(f"({x},{y}) ")
        elif key.endswith("_box"):
            if key not in d:
                d[key] = [None, None]
            # 仅保留最后取得两个点
            d[key][0] = d[key][1]
            d[key][1] = (x, y)
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

    if len(d) != len(keys):
        print("标定点数不够，标定失败")
        return

    dump_json(d, out_file)
    print(d)
    print("标定成功")


######################################## 归一化 ########################################


def normalize_coords(d: dict):
    """归一化坐标"""
    app_box = d["app_box"]

    l0, t0 = app_box[0]
    r0, b0 = app_box[1]
    w, h = r0 - l0, b0 - t0

    def _cvt(item):
        if isinstance(item, Sequence) and isinstance(item[0], Sequence):
            return tuple(_cvt(subitem) for subitem in item)
        return (item[0] - l0) / w, (item[1] - t0) / h

    return {k: _cvt(v) for k, v in d.items()}


@app.command()
def norm(
    calib_file: Path = typer.Argument("config/calib.json", help="标定文件"),
    config_file: Path = typer.Argument("config/config.json", help="配置文件"),
):
    """根据标定文件更新归一化坐标，并更新到配置文件中"""
    d = read_json(calib_file)
    locations = normalize_coords(d)
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
        d = read_json(calib_file)
        locations = normalize_coords(d)
        l0, t0 = d["app_box"][0]
        r0, b0 = d["app_box"][1]
        skill_boxes = [locations[f"skill{i + 1}_box"] for i in range(3)]
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
START_BUTTON = os.path.join(IMAGE_ROOT, "start.png")
SKILL_SELECT_SCENE = os.path.join(IMAGE_ROOT, "skill_select.png")
TUTENG_SELECT_SCENE = os.path.join(IMAGE_ROOT, "tuteng_select.png")
GUOGUAN_SCENE = os.path.join(IMAGE_ROOT, "guoguan.png")
END_SCENE = os.path.join(IMAGE_ROOT, "end.png")
ADD_TEAMER_BUTTON = os.path.join(IMAGE_ROOT, "add_teamer.png")
YIJIANYAOQING_BUTTON = os.path.join(IMAGE_ROOT, "yijianyaoqing.png")


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
    print(f"app box: (l,t,r,b) = {l0},{t0},{r0},{b0}")
    print(f"app box: (l,t,w,h) = {l0},{t0},{r0 - l0},{b0 - t0}")
    return l0, t0, r0, b0


######################################## 初级刷图 ########################################


@app.command()
def flow1(
    conf_file: Path = typer.Argument("config/config.json", help="配置文件"),
    repeat_num: int = typer.Option(1, "-r", help="刷图次数"),
    continue_flag: bool = typer.Option(False, "-c", help="是否继续当前挑战"),
    with_teams: bool = typer.Option(False, "-t", help="是否组队"),
):
    """刷图"""
    conf = read_json(conf_file)
    # 小程序位置
    l0, t0 = conf["app_box"][0]
    r0, b0 = conf["app_box"][1]
    w0 = r0 - l0
    h0 = b0 - t0
    region = (l0, t0, w0, h0)
    confidence = conf["confidence"]
    locations = conf["locations"]
    skill_boxes = [locations[f"skill{i + 1}_box"] for i in range(3)]
    steer_point = locations["steer_point"]

    pg.PAUSE = 0.01

    def _click_button(button: str):
        """点击按钮"""
        center = pg.locateCenterOnScreen(button, region=region, confidence=confidence)
        # 未找到按钮
        if not center:
            print(f"未找到按钮: {button}")
            return False
        pg.click(*center)
        return True

    def _click_button_with_retry(button: str, retry: int):
        for _ in range(retry):
            success = _click_button(button)
            if success:
                return True
            time.sleep(0.5)
        else:
            return False

    def _click_point(point: Point):
        rel_x, rel_y = point
        x = l0 + rel_x * w0
        y = t0 + rel_y * h0
        pg.click(x, y, duration=0.2)

    def _click_skill(box: Box):
        """选技能"""
        rel_l, rel_t = box[0]
        rel_r, rel_b = box[1]
        cen_x = l0 + (rel_l + rel_r) / 2 * w0
        cen_y = t0 + (rel_t + rel_b) / 2 * h0
        pg.click(cen_x, cen_y)

    def _select_skill_randomly():
        """随机选个技能"""
        i = random.randint(0, 2)
        _click_skill(skill_boxes[i])

    def _check_scene(scene: str):
        """判定是否为场景 scene"""
        center = pg.locateCenterOnScreen(scene, region=region, confidence=confidence)
        if center:
            return True
        else:
            return False

    def _wait_for_scene(scene: str, timeout: int = -1, inverse: bool = False):
        """等待场景出现/消失"""
        s = time.time()
        cnt = 0
        while True:
            center = pg.locateCenterOnScreen(
                scene, region=region, confidence=confidence
            )
            if not inverse and center:
                return True
            if inverse and not center:
                return True
            if 0 < timeout < time.time() - s:
                return False
            cnt += 1
            if cnt % 10 == 0:
                print(f"wait for scene: {scene}")

            time.sleep(0.1)

    def _attack_and_move():
        """走A"""
        rel_x0, rel_y0 = steer_point
        x = l0 + rel_x0 * w0
        y = t0 + rel_y0 * h0

        pg.moveTo(x, y)
        pg.drag(None, -0.1 * h0, 0.2)

    def _move_up():
        rel_x0, rel_y0 = steer_point
        x = l0 + rel_x0 * w0
        y = t0 + rel_y0 * h0

        pg.moveTo(x, y)
        pg.drag(None, -0.7 * h0, 0.5, pg.easeOutQuad)

    def _flow():
        """刷图流程"""
        # 邀请队友后开始
        if with_teams:
            while True:
                _click_point((0.6, 0.64))
                time.sleep(1)
                if _click_button(START_BUTTON):
                    break
                _click_point((0.5, 0.825))
                time.sleep(1)
                if _click_button(START_BUTTON):
                    break
                _click_point((0.5, 0.22))
                _click_point((0.5, 0.825))
                if _click_button(START_BUTTON):
                    break
                _click_point((0.695, 0.825))
                time.sleep(1)
                if _click_button(START_BUTTON):
                    break
                time.sleep(1)
                _click_point((0.5, 0.825))
                time.sleep(1)
                if _click_button(START_BUTTON):
                    break
                time.sleep(1)
        else:
            # 直接开始
            for _ in range(10):
                started = _click_button(START_BUTTON)
                if continue_flag or started:
                    break
                time.sleep(0.5)
            else:  # 连续10次未找到开始按钮则退出此轮流程
                return

        step_num = 2

        skill_index = 0
        loop_cnt = -1
        stage_cnt = 0
        new_stage = False
        beat_boss = False
        while True:
            loop_cnt += 1

            # TODO 改为多线程写法

            # 判定是否选择技能
            if loop_cnt % step_num == 0:
                if _check_scene(SKILL_SELECT_SCENE):
                    skill_index += 1
                    print(f"选择第{skill_index}个技能...")
                    time.sleep(0.5)
                    _select_skill_randomly()
                    time.sleep(0.5)
                    beat_boss = True

            # 判定是否选择图腾
            if loop_cnt % step_num == 1:
                if _check_scene(TUTENG_SELECT_SCENE):
                    print(f"选择图腾技能...")
                    _click_point((0.5, 0.8))
                    time.sleep(1)
                    beat_boss = True

            # 判定是否结束
            if _check_scene(END_SCENE):
                print("挑战结束...")
                _click_point((0.5, 0.95))
                time.sleep(1)
                break

            # 判定过关画面
            if beat_boss:
                if _check_scene(GUOGUAN_SCENE):
                    print(f"第{stage_cnt}关通过...")
                    stage_cnt += 1
                    new_stage = True
                    beat_boss = False
                    loop_cnt = 0
                    time.sleep(0.5)

            # 走A
            _attack_and_move()
            time.sleep(0.1)
            if loop_cnt > 10:
                if new_stage:
                    new_stage = False
                    if stage_cnt >= 4:
                        time.sleep(0.2)
                        _click_point(locations["zhoushu2_point"])
                        time.sleep(0.2)
                        _click_point(locations["zhoushu1_point"])

                    if stage_cnt >= 8:
                        time.sleep(0.2)
                        _click_point(locations["huanshen_point"])
                        time.sleep(0.2)
                        _click_point(locations["zhaohuan_point"])

        time.sleep(1)

    for i in range(repeat_num):
        print(f"第 {i + 1} 轮开始... ")
        _flow()
        print(f"第 {i + 1} 轮结束 ")


@app.command("show")
def show_capture_coords(
    height: int = typer.Option(1122, "-h", help="小程序窗口高"),
    width: int = typer.Option(600, "-w", help="小程序窗口宽"),
):
    """显示截图的坐标，配合微信截图使用"""

    def on_click(x, y, button, pressed):
        if pressed:
            print(f"({x},{y})  {x/width},{y/height}")
        else:
            print(f"({x},{y})  {x/width},{y/height}")
            return False

    with pynput.mouse.Listener(on_click=on_click) as listener:
        listener.join()


@app.command()
def version():
    """打印版本信息"""
    from . import __version__

    print(f"""飞到绝技等系列游戏辅助工具箱 (v{__version__}) """)


def main():
    try:
        app()
    except Exception as e:
        typer.echo(e)


if __name__ == "__main__":
    main()

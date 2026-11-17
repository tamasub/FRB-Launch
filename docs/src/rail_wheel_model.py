"""丸いぐりぐりレールの左右判定（Qt非依存）。"""


def rail_target_from_x(x, width):
    """中央の縦線より左はFiles Exp、中央以上はFiles List。"""
    return 'files_exp' if x < width / 2 else 'directory'


def rail_long_press_consumed(elapsed_ms, threshold_ms=450):
    """長押しのリリースはクリック操作として確定させない。"""
    return elapsed_ms >= threshold_ms

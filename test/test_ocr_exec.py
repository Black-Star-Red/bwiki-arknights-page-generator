import pytest

from shared.services.ocr_service import ocr_exec

def test_ocr_exec():
    result = ocr_exec(r"F:\项目\arknights_toolbox\photo\凯尔希·思衡托.jpg")
    print(result)
    assert result == "社会学、基础医学、生命科学、矿石病病理研究"

def test_ocr_exec2():
    result = ocr_exec(r"F:\项目\arknights_toolbox\photo\可露希尔.jpg")
    print(result)
    assert result == "全领域工程"

def test_ocr_exec3():
    result = ocr_exec(r"F:\项目\arknights_toolbox\photo\裂响.jpg")
    print(result)
    assert result == "搬运、清洗、现浇混凝土"

def test_ocr_exec4():
    result = ocr_exec(r"F:\项目\arknights_toolbox\photo\贝洛内.jpg")
    print(result)
    assert result == "情报搜集、商业经营、烹饪与调酒"

def test_ocr_exec5():
    result = ocr_exec(r"F:\项目\arknights_toolbox\photo\望.jpg")
    print(result)
    assert result == "兵法、围棋、政治"

def test_ocr_exec6():
    result = ocr_exec(r"F:\项目\arknights_toolbox\photo\复奏.jpg")
    print(result)
    assert result == "财务管理、乐团经营、商务谈判"
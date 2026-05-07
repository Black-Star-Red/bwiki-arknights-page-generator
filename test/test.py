import pytest

from arknights_toolbox.shared.services.bilibili_service import get_dynamic_id

def test_get_dynamic_id(name:str):
    id = get_dynamic_id(name)
    assert id=="6051",id

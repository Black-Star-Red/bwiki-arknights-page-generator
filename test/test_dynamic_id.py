import pytest

from shared.services.bilibili_service import get_dynamic_id

def test_get_dynamic_id():
    id = get_dynamic_id("凯尔希·思衡托")
    assert id=="6051",id

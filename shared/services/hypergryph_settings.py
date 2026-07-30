

def resolve_hypergryph_settings(config: dict) -> dict:
    hg = config.get("hypergryph") if isinstance(config.get("hypergryph"), dict) else {}
    return {
        "bulletin_list_url": hg["bulletin_list_url"],
        "bulletin_detail_url": hg["bulletin_detail_url"],
        "bulletin_target": hg.get("bulletin_target") or "Android",
        "dynamic_compile_url": hg.get("dynamic_compile_url"),  # 可选
    }
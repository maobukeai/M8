def is_chinese(word: str):
    """检查字符是否存在中文"""
    for ch in str(word):
        if '\u4e00' <= ch <= '\u9fff':
            return True
    return False


def is_all_chinese(string: str):
    """检验字符是否全是中文"""
    for c in string:
        if not ('\u4e00' <= c <= '\u9fa5'):
            return False
    return True


def is_contains_chinese(text: str):
    """通过re检查"""
    if not isinstance(text, str):
        return False
    import re
    pattern = re.compile(r'[\u4e00-\u9fff]+')
    return bool(pattern.search(text))

"""'drop' as substring in helper names — should produce NO findings."""


def _drop_dashes(text: str) -> str:
    """String cleanup — NOT a database delete."""
    return text.replace("-", "")


def clean_dataframe(df):
    """Pandas operations — NOT database deletes."""
    df = df.drop_duplicates()
    df = df.dropna()
    return df


def fetch_data(url: str):
    """Uses _drop_dashes internally — NOT a delete."""
    clean_url = _drop_dashes(url)
    return clean_url

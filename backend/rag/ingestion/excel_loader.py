import pandas as pd

SITUATION_MAP = {
    "위반 의심 사항": "suspected",
    "거래 진행 중": "in_progress",
    "계약 체결 전": "contract_before",
    "정기 점검": "regular_check"
}


def load_scenarios(excel_path: str) -> pd.DataFrame:
    df = pd.read_excel(excel_path, sheet_name="전체_QA", header=1)
    df["situation_type_en"] = df["상황유형"].map(SITUATION_MAP)
    return df


def filter_by_situation(df: pd.DataFrame, situation_type: str) -> pd.DataFrame:
    return df[df["situation_type_en"] == situation_type].reset_index(drop=True)
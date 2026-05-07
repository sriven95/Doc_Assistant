import os
import pandas as pd
from typing import List, Dict, Optional


def _load_df(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Excel file not found: {path}")
    return pd.read_excel(path, engine="openpyxl")


def get_events_for_patient(
    person_id: str,
    input_file: str,
) -> List[Dict]:
    """
    Return all event rows for a patient from input Excel.
    Each row contains event_id, doc_type, plain_scrubbed_text.
    Order preserved as natural Excel row order (newest first).
    firstname, lastname, scrubbed_embedding, event_end_dt_tm are excluded.
    """
    df = _load_df(input_file)
    mask = df["person_id"].astype(str).str.strip() == str(person_id).strip()
    rows = df[mask]

    events = []
    for _, row in rows.iterrows():
        events.append({
            "event_id"           : str(row.get("event_id", "")).strip(),
            "doc_type"           : str(row.get("doc_type", "N/A")).strip(),
            "plain_scrubbed_text": str(row.get("plain_scrubbed_text", "")).strip(),
        })
    return events


def get_all_person_ids(input_file: str) -> List[str]:
    """
    Return sorted list of all unique person_ids from input Excel.
    """
    df = _load_df(input_file)
    return sorted(df["person_id"].dropna().astype(str).str.strip().unique().tolist())


def get_patient_summary(
    person_id: str,
    output_file: str,
) -> Optional[Dict]:
    """
    Return the generated summary for a patient from output Excel.
    Returns None if not found.
    """
    if not os.path.exists(output_file):
        return None

    df = _load_df(output_file)
    mask = df["person_id"].astype(str).str.strip() == str(person_id).strip()
    rows = df[mask]

    if rows.empty:
        return None

    row = rows.iloc[0]
    return {
        "person_id"           : str(row.get("person_id", "")),
        "main_subject"        : str(row.get("main_subject", "")),
        "summary_chain"       : str(row.get("summary_chain", "")),
        "processed_event_ids" : str(row.get("processed_event_ids", "")),
        "event_count"         : int(row.get("event_count", 0)),
        "model_id"            : str(row.get("model_id", "")),
        "generated_at"        : str(row.get("generated_at", "")),
        "last_updated_at"     : str(row.get("last_updated_at", "")),
    }

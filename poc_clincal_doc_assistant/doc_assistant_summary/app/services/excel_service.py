import os
import pandas as pd
from typing import List, Dict, Optional
from datetime import datetime

from app.config import settings
from app.core.logging import logger


# ── INPUT EXCEL ────────────────────────────────────────────────────────────────

def read_input_excel(file_path: Optional[str] = None) -> pd.DataFrame:
    """
    Read the input Excel file into a DataFrame.
    Validates that all required columns are present.
    Raises FileNotFoundError or ValueError on failure.
    """
    path = file_path or settings.input_file
    if not os.path.exists(path):
        raise FileNotFoundError(f"Input Excel not found: {path}")

    df = pd.read_excel(path, engine="openpyxl")
    logger.info(f"Input Excel loaded | rows={len(df)} | path={path}")

    required_cols = [
        settings.col_event_id,
        settings.col_person_id,
        settings.col_scrubbed_text,
    ]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Required columns missing from input Excel: {missing}")

    return df


def get_all_patients(file_path: Optional[str] = None) -> Dict[str, List[Dict]]:
    """
    Read input Excel and group all rows by person_id.
    Row order is preserved as-is (natural Excel order = newest first).

    Returns: { person_id: [event_dict, ...] }
    """
    df = read_input_excel(file_path)
    patients: Dict[str, List[Dict]] = {}

    for _, row in df.iterrows():
        person_id = str(row[settings.col_person_id]).strip()
        event = {
            "event_id"           : str(row.get(settings.col_event_id, "")).strip(),
            "doc_type"           : str(row.get(settings.col_doc_type, "N/A")).strip(),
            "plain_scrubbed_text": str(row.get(settings.col_scrubbed_text, "")).strip(),
            "run_id"             : str(row.get(settings.col_run_id, "")).strip(),
            "model_id"           : str(row.get(settings.col_model_id, "")).strip(),
        }
        patients.setdefault(person_id, []).append(event)

    logger.info(f"Patients grouped | total={len(patients)}")
    return patients


def get_events_for_patient(
    person_id: str,
    file_path: Optional[str] = None,
) -> List[Dict]:
    """
    Return all events for a specific patient in natural Excel row order.
    """
    return get_all_patients(file_path).get(person_id, [])


def get_single_event(
    event_id: str,
    file_path: Optional[str] = None,
) -> Optional[Dict]:
    """
    Fetch one event row by event_id from the input Excel.
    Returns None if not found.
    """
    df = read_input_excel(file_path)
    matches = df[df[settings.col_event_id].astype(str).str.strip() == event_id]
    if matches.empty:
        logger.warning(f"event_id not found in input Excel | event_id={event_id}")
        return None

    r = matches.iloc[0]
    return {
        "event_id"           : str(r.get(settings.col_event_id, "")).strip(),
        "doc_type"           : str(r.get(settings.col_doc_type, "N/A")).strip(),
        "plain_scrubbed_text": str(r.get(settings.col_scrubbed_text, "")).strip(),
        "run_id"             : str(r.get(settings.col_run_id, "")).strip(),
        "model_id"           : str(r.get(settings.col_model_id, "")).strip(),
    }


# ── OUTPUT EXCEL ───────────────────────────────────────────────────────────────

def _load_output_df() -> pd.DataFrame:
    """Load output Excel or return empty DataFrame with correct columns."""
    if os.path.exists(settings.output_file):
        return pd.read_excel(settings.output_file, engine="openpyxl")

    return pd.DataFrame(columns=[
        settings.out_person_id,
        settings.out_main_subject,
        settings.out_summary_chain,
        settings.out_processed_events,
        settings.out_event_count,
        settings.out_model_id,
        settings.out_generated_at,
        settings.out_last_updated_at,
    ])


def _save_output_df(df: pd.DataFrame) -> None:
    """Save DataFrame to output Excel, creating directories if needed."""
    os.makedirs(os.path.dirname(settings.output_file), exist_ok=True)
    df.to_excel(settings.output_file, index=False, engine="openpyxl")
    logger.debug(f"Output Excel saved | rows={len(df)}")


def get_existing_summary(person_id: str) -> Optional[Dict]:
    """
    Look up an existing summary for a person_id in the output Excel.
    Returns the row as a dict or None if not found.
    """
    df = _load_output_df()
    mask = df[settings.out_person_id].astype(str).str.strip() == person_id
    if not mask.any():
        return None

    r = df[mask].iloc[0]
    raw_events = str(r.get(settings.out_processed_events, "")).strip()
    processed_event_ids = [e.strip() for e in raw_events.split(",") if e.strip()]

    return {
        "person_id"           : str(r[settings.out_person_id]),
        "main_subject"        : str(r.get(settings.out_main_subject, "")),
        "summary_chain"       : str(r.get(settings.out_summary_chain, "")),
        "processed_event_ids" : processed_event_ids,
        "event_count"         : int(r.get(settings.out_event_count, 0)),
        "model_id"            : str(r.get(settings.out_model_id, "")),
        "generated_at"        : str(r.get(settings.out_generated_at, "")),
        "last_updated_at"     : str(r.get(settings.out_last_updated_at, "")),
    }


def write_summary(
    person_id: str,
    main_subject: str,
    summary_chain: str,
    processed_event_ids: List[str],
    generated_at: Optional[str] = None,
) -> None:
    """
    Write or overwrite a summary row in the output Excel.
    Creates the file if it does not exist yet.
    """
    df  = _load_output_df()
    now = datetime.utcnow().isoformat()

    new_row = {
        settings.out_person_id       : person_id,
        settings.out_main_subject    : main_subject,
        settings.out_summary_chain   : summary_chain,
        settings.out_processed_events: ", ".join(processed_event_ids),
        settings.out_event_count     : len(processed_event_ids),
        settings.out_model_id        : settings.gemini_model,
        settings.out_generated_at    : generated_at or now,
        settings.out_last_updated_at : now,
    }

    mask = df[settings.out_person_id].astype(str).str.strip() == person_id
    if mask.any():
        for key, val in new_row.items():
            df.loc[mask, key] = val
        logger.info(f"Summary updated in output Excel | person_id={person_id}")
    else:
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        logger.info(f"Summary written to output Excel | person_id={person_id}")

    _save_output_df(df)

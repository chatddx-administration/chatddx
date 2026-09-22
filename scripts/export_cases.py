#!/usr/bin/env python3

from pathlib import Path

import psycopg

DB = "chatddx_old"

root = Path("expects")

with psycopg.connect(f"dbname={DB}") as conn:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT tc.name AS testcase_name, d.pattern AS diagnosis_pattern FROM api_ddxtestcase tc JOIN api_ddxtestcase_diagnoses td ON tc.id = td.ddxtestcase_id JOIN api_diagnosis d ON td.diagnosis_id = d.id"
        )

        for name, content in cur:
            (root / name.replace(" ", "_")).write_text(content + "\n")

#!/usr/bin/env python3
"""Configure Superset for goldlayer demo: DB connection, datasets, roles, users, RLS.

Run: python dev/setup_superset.py
Requires: requests
"""
import json
import sys

import requests

BASE = "http://localhost:8088"
VIEWS = [
    "delay_vw",
    "congestion_rate_vw",
    "punctuality_index_vw",
    "ridership_vw",
    "number_of_trips_vw",
    "number_of_stops_vw",
]


def login(session: requests.Session) -> str:
    resp = session.post(f"{BASE}/api/v1/security/login", json={
        "username": "admin",
        "password": "admin",
        "provider": "db",
        "refresh": True,
    })
    resp.raise_for_status()
    token = resp.json()["access_token"]
    session.headers["Authorization"] = f"Bearer {token}"

    csrf_resp = session.get(f"{BASE}/api/v1/security/csrf_token/")
    csrf_resp.raise_for_status()
    csrf = csrf_resp.json()["result"]
    session.headers["X-CSRFToken"] = csrf
    session.headers["Referer"] = BASE
    return token


def create_database(session: requests.Session) -> int:
    # Check if already exists
    resp = session.get(f"{BASE}/api/v1/database/")
    if resp.ok:
        for db in resp.json().get("result", []):
            if db["database_name"] == "KPI Data (goldlayer)":
                db_id = db["id"]
                print(f"Database already exists (id={db_id}), skipping.")
                return db_id

    resp = session.post(f"{BASE}/api/v1/database/", json={
        "database_name": "KPI Data (goldlayer)",
        "sqlalchemy_uri": "postgresql://superset:superset@db:5432/superset",
        "extra": json.dumps({"metadata_params": {}, "engine_params": {}, "schemas_allowed_for_file_upload": []}),
        "expose_in_sqllab": True,
        "allow_run_async": False,
    })
    if not resp.ok:
        print(f"Failed to create database: {resp.status_code} {resp.text}")
        sys.exit(1)
    db_id = resp.json()["id"]
    print(f"Created database id={db_id}")
    return db_id


def create_datasets(session: requests.Session, db_id: int) -> list[int]:
    dataset_ids = []
    # Cache existing datasets (use large page_size to avoid pagination issues)
    existing = {}
    resp = session.get(f"{BASE}/api/v1/dataset/?q=(page_size:200)")
    if resp.ok:
        for ds in resp.json().get("result", []):
            if ds.get("schema") == "goldlayer":
                existing[ds["table_name"]] = ds["id"]

    for view in VIEWS:
        if view in existing:
            ds_id = existing[view]
            print(f"Dataset {view} already exists (id={ds_id}), skipping.")
            dataset_ids.append(ds_id)
            continue

        resp = session.post(f"{BASE}/api/v1/dataset/", json={
            "database": db_id,
            "schema": "goldlayer",
            "table_name": view,
        })
        if not resp.ok:
            print(f"Failed to create dataset {view}: {resp.status_code} {resp.text}")
            continue
        ds_id = resp.json()["id"]
        print(f"Created dataset {view} id={ds_id}")
        dataset_ids.append(ds_id)
    return dataset_ids


def get_or_create_role(session: requests.Session, name: str) -> int:
    resp = session.get(f"{BASE}/api/v1/security/roles/?q=(page_size:200)")
    if resp.ok:
        for role in resp.json().get("result", []):
            if role["name"] == name:
                role_id = role["id"]
                print(f"Role '{name}' already exists (id={role_id}).")
                return role_id

    resp = session.post(f"{BASE}/api/v1/security/roles/", json={"name": name})
    if not resp.ok:
        print(f"Failed to create role {name}: {resp.status_code} {resp.text}")
        sys.exit(1)
    role_id = resp.json()["id"]
    print(f"Created role '{name}' id={role_id}")
    return role_id


def get_role_id_by_name(session: requests.Session, name: str) -> int:
    resp = session.get(f"{BASE}/api/v1/security/roles/")
    resp.raise_for_status()
    for role in resp.json().get("result", []):
        if role["name"] == name:
            return role["id"]
    raise RuntimeError(f"Role '{name}' not found")


def get_gamma_role_id(session: requests.Session) -> int:
    resp = session.get(f"{BASE}/api/v1/security/roles/")
    resp.raise_for_status()
    for role in resp.json().get("result", []):
        if role["name"] == "Gamma":
            return role["id"]
    raise RuntimeError("Gamma role not found")


def create_user(session: requests.Session, username: str, password: str, role_ids: list[int]) -> None:
    resp = session.get(f"{BASE}/api/v1/security/users/")
    if resp.ok:
        for u in resp.json().get("result", []):
            if u["username"] == username:
                print(f"User '{username}' already exists, skipping.")
                return

    resp = session.post(f"{BASE}/api/v1/security/users/", json={
        "active": True,
        "email": f"{username}@demo.local",
        "first_name": username,
        "last_name": "Demo",
        "username": username,
        "password": password,
        "roles": role_ids,
    })
    if not resp.ok:
        print(f"Failed to create user {username}: {resp.status_code} {resp.text}")
    else:
        print(f"Created user '{username}'")


def create_rls_filter(session: requests.Session, name: str, clause: str, role_id: int, dataset_ids: list[int]) -> None:
    resp = session.get(f"{BASE}/api/v1/rowlevelsecurity/")
    if resp.ok:
        for f in resp.json().get("result", []):
            if f["name"] == name:
                print(f"RLS filter '{name}' already exists, skipping.")
                return

    resp = session.post(f"{BASE}/api/v1/rowlevelsecurity/", json={
        "name": name,
        "clause": clause,
        "filter_type": "Regular",
        "tables": dataset_ids,
        "roles": [role_id],
        "group_key": "",
        "description": "",
    })
    if not resp.ok:
        print(f"Failed to create RLS filter '{name}': {resp.status_code} {resp.text}")
    else:
        print(f"Created RLS filter '{name}'")


def main():
    session = requests.Session()
    session.headers["Content-Type"] = "application/json"

    print("Logging in...")
    login(session)

    print("\nCreating database connection...")
    db_id = create_database(session)

    print("\nCreating datasets...")
    dataset_ids = create_datasets(session, db_id)

    print("\nCreating roles...")
    alpha_id = get_role_id_by_name(session, "Alpha")
    sqllib_id = get_role_id_by_name(session, "sql_lab")
    atm_role_id = get_or_create_role(session, "operator_atm")
    gtt_role_id = get_or_create_role(session, "operator_gtt")

    print("\nCreating users...")
    create_user(session, "atm_user", "atm_pass123", [alpha_id, sqllib_id, atm_role_id])
    create_user(session, "gtt_user", "gtt_pass123", [alpha_id, sqllib_id, gtt_role_id])

    print("\nCreating RLS filters...")
    if dataset_ids:
        create_rls_filter(session, "ATM tenant filter", "tenant_id = 1", atm_role_id, dataset_ids)
        create_rls_filter(session, "GTT tenant filter", "tenant_id = 2", gtt_role_id, dataset_ids)

    print("\nDone. Users: atm_user/atm_pass123, gtt_user/gtt_pass123")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Generate multi-tenant demo data for goldlayer schema.

Run: python dev/seed_goldlayer.py
Requires: psycopg2-binary
"""
import random
from datetime import datetime, timedelta

import psycopg2

DSN = "host=localhost port=5432 dbname=superset user=superset password=superset"

TENANTS = [
    {
        "tenant_id": 1,
        "name": "ATM Milano",
        "lines": [
            {
                "line_id": "M1",
                "line_name": "Metro M1",
                "destinations": ["SESTO FS", "RHO FIERA"],
                "stops": [
                    ("S01", "Duomo",    45.4641, 9.1919),
                    ("S02", "Cadorna",  45.4662, 9.1771),
                    ("S03", "Loreto",   45.4855, 9.2268),
                    ("S04", "Sesto FS", 45.5360, 9.2327),
                ],
            },
            {
                "line_id": "M2",
                "line_name": "Metro M2",
                "destinations": ["GESSATE", "ASSAGO"],
                "stops": [
                    ("S05", "Centrale",  45.4851, 9.2035),
                    ("S06", "Garibaldi", 45.4839, 9.1881),
                    ("S07", "Romolo",    45.4482, 9.1601),
                    ("S08", "Assago",    45.4063, 9.1235),
                ],
            },
        ],
    },
    {
        "tenant_id": 2,
        "name": "GTT Torino",
        "lines": [
            {
                "line_id": "4",
                "line_name": "Tram 4",
                "destinations": ["PILONETTO", "COLLEGNO"],
                "stops": [
                    ("T01", "Porta Nuova", 45.0628, 7.6786),
                    ("T02", "Re Umberto",  45.0681, 7.6598),
                    ("T03", "Ospedale",    45.0732, 7.6512),
                    ("T04", "Collegno",    45.0789, 7.5821),
                ],
            },
            {
                "line_id": "9",
                "line_name": "Bus 9",
                "destinations": ["NIZZA MILLEFONTI", "GROSSETO"],
                "stops": [
                    ("T05", "Lingotto", 44.9966, 7.6782),
                    ("T06", "Marconi",  45.0451, 7.6677),
                    ("T07", "Crocetta", 45.0601, 7.6701),
                    ("T08", "Grosseto", 45.0714, 7.6631),
                ],
            },
        ],
    },
]

DIRECTIONS = ["outbound", "inbound"]
WEEKS = 12
NOW = datetime.now()
# Start from 12 weeks ago, each timeslot is 1 week Mon 07:00 → Mon 22:00
FIRST_MONDAY = NOW - timedelta(weeks=WEEKS)
FIRST_MONDAY = FIRST_MONDAY - timedelta(days=FIRST_MONDAY.weekday())
FIRST_MONDAY = FIRST_MONDAY.replace(hour=7, minute=0, second=0, microsecond=0)

rng = random.Random(42)


def week_slots():
    for w in range(WEEKS):
        start = FIRST_MONDAY + timedelta(weeks=w)
        end = start + timedelta(hours=15)  # 07:00 → 22:00
        yield start, end


def r_int(lo, hi):
    return rng.randint(lo, hi)


def r_float(lo, hi):
    return round(rng.uniform(lo, hi), 4)


def seed(conn):
    cur = conn.cursor()
    ts = NOW

    delay_rows = []
    congestion_rows = []
    punctuality_rows = []
    ridership_rows = []
    trips_rows = []
    stops_rows = []

    for tenant in TENANTS:
        tid = tenant["tenant_id"]
        for line in tenant["lines"]:
            lid = line["line_id"]
            lname = line["line_name"]
            for direction in DIRECTIONS:
                dest = line["destinations"][0] if direction == "outbound" else line["destinations"][1]
                for start, end in week_slots():
                    # number_of_trips: one row per (week, line, direction)
                    exp_trips = r_int(80, 120)
                    comp_trips = r_int(int(exp_trips * 0.85), exp_trips)
                    late_trips = r_int(0, int(comp_trips * 0.15))
                    early_trips = r_int(0, int(comp_trips * 0.05))
                    trips_rows.append((start, end, tid, lid, lname, direction, dest,
                                       exp_trips, comp_trips, late_trips, early_trips, ts))

                    for stop_id, stop_name, lat, lon in line["stops"]:
                        mean_in = r_int(-30, 90)
                        mean_out = r_int(-30, 90)
                        min_in = mean_in - r_int(5, 20)
                        max_in = mean_in + r_int(5, 40)
                        min_out = mean_out - r_int(5, 20)
                        max_out = mean_out + r_int(5, 40)

                        delay_rows.append((
                            start, end, tid, lid, lname, dest, direction, stop_id, stop_name, lat, lon,
                            min_in, mean_in, r_int(5, 15), max_in,
                            min_out, mean_out, r_int(5, 15), max_out,
                            ts,
                        ))

                        min_cr = r_float(0.0, 0.3)
                        mean_cr = min_cr + r_float(0.0, 0.4)
                        max_cr = mean_cr + r_float(0.0, 0.3)
                        congestion_rows.append((
                            start, end, tid, lid, lname, dest, direction, stop_id, stop_name, lat, lon,
                            min_cr, mean_cr, r_float(0.0, 0.1), max_cr,
                            ts,
                        ))

                        total = r_int(200, 800)
                        soft = r_int(int(total * 0.5), int(total * 0.75))
                        medium = r_int(int(total * 0.1), int(total * 0.25))
                        hard = r_int(0, int(total * 0.1))
                        outside = total - soft - medium - hard
                        if outside < 0:
                            outside = 0
                        punctuality_rows.append((
                            start, end, tid, lid, lname, dest, direction, stop_id, stop_name, lat, lon,
                            hard, medium, soft, outside,
                            r_int(0, hard), r_int(0, medium), r_int(0, soft), r_int(0, outside),
                            ts,
                        ))

                        boarding = r_int(50, 300)
                        alighting = r_int(50, 300)
                        tot_r = r_int(100, 500)
                        ridership_rows.append((
                            start, end, tid, lid, lname, dest, direction, stop_id, stop_name, lat, lon,
                            boarding, alighting, tot_r, r_int(50, 200), r_int(200, 600),
                            ts,
                        ))

                        sched = r_int(80, 120)
                        comp = r_int(int(sched * 0.85), sched)
                        late = r_int(0, int(comp * 0.15))
                        early = r_int(0, int(comp * 0.05))
                        stops_rows.append((
                            start, end, tid, lid, lname, dest, direction, stop_id, stop_name, lat, lon,
                            sched, comp, late, early,
                            ts,
                        ))

    cur.executemany(
        """INSERT INTO goldlayer.delay VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
           ON CONFLICT DO NOTHING""",
        delay_rows,
    )
    cur.executemany(
        """INSERT INTO goldlayer.congestion_rate VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
           ON CONFLICT DO NOTHING""",
        congestion_rows,
    )
    cur.executemany(
        """INSERT INTO goldlayer.punctuality_index VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
           ON CONFLICT DO NOTHING""",
        punctuality_rows,
    )
    cur.executemany(
        """INSERT INTO goldlayer.ridership VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
           ON CONFLICT DO NOTHING""",
        ridership_rows,
    )
    cur.executemany(
        """INSERT INTO goldlayer.number_of_trips VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
           ON CONFLICT DO NOTHING""",
        trips_rows,
    )
    cur.executemany(
        """INSERT INTO goldlayer.number_of_stops VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
           ON CONFLICT DO NOTHING""",
        stops_rows,
    )

    conn.commit()
    cur.close()
    print(f"Inserted: {len(delay_rows)} delay, {len(congestion_rows)} congestion_rate, "
          f"{len(punctuality_rows)} punctuality_index, {len(ridership_rows)} ridership, "
          f"{len(trips_rows)} number_of_trips, {len(stops_rows)} number_of_stops")


if __name__ == "__main__":
    conn = psycopg2.connect(DSN)
    seed(conn)
    conn.close()
    print("Done.")

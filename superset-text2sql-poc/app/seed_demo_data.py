import random
from datetime import date, datetime, timedelta
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Date, ForeignKey, Text,
    create_engine, MetaData, Table
)
from sqlalchemy.orm import declarative_base
from app.config import settings

Base = declarative_base()


class Line(Base):
    __tablename__ = "lines"
    line_id = Column(Integer, primary_key=True)
    line_name = Column(String(50), nullable=False)
    mode = Column(String(20), nullable=False)
    operator_name = Column(String(100), nullable=False)


class Trip(Base):
    __tablename__ = "trips"
    trip_id = Column(Integer, primary_key=True)
    line_id = Column(Integer, ForeignKey("lines.line_id"), nullable=False)
    service_date = Column(Date, nullable=False)
    direction = Column(String(10), nullable=False)
    scheduled_start_time = Column(DateTime, nullable=False)
    actual_start_time = Column(DateTime, nullable=False)
    scheduled_end_time = Column(DateTime, nullable=False)
    actual_end_time = Column(DateTime, nullable=False)
    status = Column(String(20), nullable=False)


class StopEvent(Base):
    __tablename__ = "stop_events"
    event_id = Column(Integer, primary_key=True)
    trip_id = Column(Integer, ForeignKey("trips.trip_id"), nullable=False)
    line_id = Column(Integer, ForeignKey("lines.line_id"), nullable=False)
    stop_id = Column(Integer, nullable=False)
    service_date = Column(Date, nullable=False)
    scheduled_arrival_time = Column(DateTime, nullable=False)
    actual_arrival_time = Column(DateTime, nullable=False)
    arrival_delay_seconds = Column(Integer, nullable=False)


class VehicleEvent(Base):
    __tablename__ = "vehicle_events"
    event_id = Column(Integer, primary_key=True)
    vehicle_id = Column(Integer, nullable=False)
    line_id = Column(Integer, ForeignKey("lines.line_id"), nullable=False)
    event_timestamp = Column(DateTime, nullable=False)
    event_type = Column(String(50), nullable=False)
    severity = Column(String(20), nullable=False)


class PassengerCount(Base):
    __tablename__ = "passenger_counts"
    count_id = Column(Integer, primary_key=True)
    line_id = Column(Integer, ForeignKey("lines.line_id"), nullable=False)
    vehicle_id = Column(Integer, nullable=False)
    event_timestamp = Column(DateTime, nullable=False)
    boarding_count = Column(Integer, nullable=False)
    alighting_count = Column(Integer, nullable=False)
    occupancy = Column(Integer, nullable=False)


LINES = [
    (1, "Line 1", "bus", "CityBus SpA"),
    (2, "Line 2", "bus", "CityBus SpA"),
    (3, "Line 3", "tram", "MetroTram Srl"),
    (4, "Line 4", "tram", "MetroTram Srl"),
    (5, "Line M1", "metro", "MetroCity"),
    (6, "Line M2", "metro", "MetroCity"),
    (7, "Line T1", "trolleybus", "ElectroCity"),
    (8, "Line T2", "trolleybus", "ElectroCity"),
]

STATUSES = ["completed", "completed", "completed", "delayed", "cancelled"]
DIRECTIONS = ["outbound", "inbound"]
EVENT_TYPES = ["diagnostic_alarm", "communication_loss", "gps_loss", "door_failure"]
SEVERITIES = ["low", "medium", "high", "critical"]


def seed():
    engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    from sqlalchemy.orm import Session
    session = Session(engine)

    # Insert lines
    for lid, lname, mode, op in LINES:
        session.add(Line(line_id=lid, line_name=lname, mode=mode, operator_name=op))
    session.commit()

    today = date.today()
    trip_id = 1
    stop_event_id = 1
    vehicle_event_id = 1
    passenger_count_id = 1

    for day_offset in range(90):
        svc_date = today - timedelta(days=day_offset)
        for line_id, _, _, _ in LINES:
            for direction in DIRECTIONS:
                scheduled_start = datetime(svc_date.year, svc_date.month, svc_date.day,
                                           random.randint(6, 22), random.randint(0, 59))
                duration_minutes = random.randint(20, 60)
                delay_start = random.randint(-60, 600)
                delay_end = random.randint(-60, 900)
                actual_start = scheduled_start + timedelta(seconds=delay_start)
                scheduled_end = scheduled_start + timedelta(minutes=duration_minutes)
                actual_end = scheduled_end + timedelta(seconds=delay_end)
                status = random.choice(STATUSES)

                session.add(Trip(
                    trip_id=trip_id,
                    line_id=line_id,
                    service_date=svc_date,
                    direction=direction,
                    scheduled_start_time=scheduled_start,
                    actual_start_time=actual_start,
                    scheduled_end_time=scheduled_end,
                    actual_end_time=actual_end,
                    status=status,
                ))

                # Stop events for this trip
                num_stops = random.randint(5, 15)
                for stop_num in range(num_stops):
                    stop_id = random.randint(1, 100)
                    scheduled_arrival = scheduled_start + timedelta(minutes=stop_num * (duration_minutes // num_stops))
                    delay_sec = random.randint(-120, 900)
                    actual_arrival = scheduled_arrival + timedelta(seconds=delay_sec)
                    session.add(StopEvent(
                        event_id=stop_event_id,
                        trip_id=trip_id,
                        line_id=line_id,
                        stop_id=stop_id,
                        service_date=svc_date,
                        scheduled_arrival_time=scheduled_arrival,
                        actual_arrival_time=actual_arrival,
                        arrival_delay_seconds=delay_sec,
                    ))
                    stop_event_id += 1

                trip_id += 1

            # Vehicle events
            num_vehicle_events = random.randint(0, 3)
            for _ in range(num_vehicle_events):
                vehicle_id = random.randint(1, 50)
                event_hour = random.randint(0, 23)
                event_ts = datetime(svc_date.year, svc_date.month, svc_date.day, event_hour, random.randint(0, 59))
                session.add(VehicleEvent(
                    event_id=vehicle_event_id,
                    vehicle_id=vehicle_id,
                    line_id=line_id,
                    event_timestamp=event_ts,
                    event_type=random.choice(EVENT_TYPES),
                    severity=random.choice(SEVERITIES),
                ))
                vehicle_event_id += 1

            # Passenger counts
            num_counts = random.randint(3, 8)
            for _ in range(num_counts):
                vehicle_id = random.randint(1, 50)
                event_hour = random.randint(6, 23)
                event_ts = datetime(svc_date.year, svc_date.month, svc_date.day, event_hour, random.randint(0, 59))
                boarding = random.randint(5, 80)
                alighting = random.randint(3, boarding)
                occupancy = random.randint(0, 120)
                session.add(PassengerCount(
                    count_id=passenger_count_id,
                    line_id=line_id,
                    vehicle_id=vehicle_id,
                    event_timestamp=event_ts,
                    boarding_count=boarding,
                    alighting_count=alighting,
                    occupancy=occupancy,
                ))
                passenger_count_id += 1

        if day_offset % 10 == 0:
            session.commit()

    session.commit()
    session.close()
    print(f"Seeded: {trip_id-1} trips, {stop_event_id-1} stop events, {vehicle_event_id-1} vehicle events, {passenger_count_id-1} passenger counts.")


if __name__ == "__main__":
    seed()

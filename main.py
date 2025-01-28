from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from databases import Database
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, DateTime, Boolean, ForeignKey

# Konfiguracja bazy danych
DATABASE_URL = "sqlite:///./test.db"  # SQLite dla środowiska lokalnego
# DATABASE_URL = "postgresql://<username>:<password>@<host>/<database>"  # PostgreSQL dla produkcji
database = Database(DATABASE_URL)
engine = create_engine(DATABASE_URL)
metadata = MetaData()

# Tabele w bazie danych
tasks_table = Table(
    "tasks",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("title", String, nullable=False, unique=True),
    Column("description", String, nullable=True),
    Column("status", String, nullable=False, default="TODO"),
)

pomodoro_table = Table(
    "pomodoro_sessions",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("task_id", Integer, ForeignKey("tasks.id"), nullable=False),
    Column("start_time", DateTime, nullable=False),
    Column("end_time", DateTime, nullable=True),
    Column("completed", Boolean, default=False),
)

# FastAPI app
app = FastAPI()

# Model Pydantic
class Task(BaseModel):
    title: str = Field(..., min_length=3, max_length=100)
    description: Optional[str] = Field(None, max_length=300)
    status: str = Field("TODO", regex="^(TODO|IN_PROGRESS|DONE)$")

class PomodoroSession(BaseModel):
    task_id: int
    start_time: datetime
    end_time: Optional[datetime] = None
    completed: bool = False

# Eventy start/stop aplikacji
@app.on_event("startup")
async def startup():
    metadata.create_all(engine)
    await database.connect()

@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()

# Endpointy CRUD dla zadań
@app.post("/tasks", status_code=201)
async def create_task(task: Task):
    query = tasks_table.insert().values(
        title=task.title,
        description=task.description,
        status=task.status,
    )
    task_id = await database.execute(query)
    return {**task.dict(), "id": task_id}

@app.get("/tasks", response_model=List[dict])
async def get_tasks(status: Optional[str] = Query(None, regex="^(TODO|IN_PROGRESS|DONE)$")):
    query = tasks_table.select()
    if status:
        query = query.where(tasks_table.c.status == status)
    return await database.fetch_all(query)

@app.get("/tasks/{task_id}")
async def get_task(task_id: int):
    query = tasks_table.select().where(tasks_table.c.id == task_id)
    task = await database.fetch_one(query)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    return task

@app.put("/tasks/{task_id}")
async def update_task(task_id: int, updated_task: Task):
    query = tasks_table.select().where(tasks_table.c.id == task_id)
    task = await database.fetch_one(query)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")

    update_query = tasks_table.update().where(tasks_table.c.id == task_id).values(
        title=updated_task.title,
        description=updated_task.description,
        status=updated_task.status,
    )
    await database.execute(update_query)
    return {**updated_task.dict(), "id": task_id}

@app.delete("/tasks/{task_id}", status_code=204)
async def delete_task(task_id: int):
    query = tasks_table.delete().where(tasks_table.c.id == task_id)
    result = await database.execute(query)
    if not result:
        raise HTTPException(status_code=404, detail="Task not found.")

# Endpointy Pomodoro
@app.post("/pomodoro", status_code=201)
async def create_pomodoro(task_id: int):
    query = tasks_table.select().where(tasks_table.c.id == task_id)
    task = await database.fetch_one(query)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")

    query = pomodoro_table.insert().values(
        task_id=task_id,
        start_time=datetime.now(),
        completed=False,
    )
    session_id = await database.execute(query)
    return {"task_id": task_id, "session_id": session_id}

@app.post("/pomodoro/{task_id}/stop")
async def stop_pomodoro(task_id: int):
    query = pomodoro_table.select().where(
        pomodoro_table.c.task_id == task_id,
        pomodoro_table.c.completed == False,
    )
    session = await database.fetch_one(query)
    if not session:
        raise HTTPException(status_code=404, detail="Active Pomodoro not found.")

    update_query = pomodoro_table.update().where(
        pomodoro_table.c.id == session["id"]
    ).values(
        end_time=datetime.now(),
        completed=True,
    )
    await database.execute(update_query)
    return {"task_id": task_id, "session_id": session["id"]}

@app.get("/pomodoro/stats")
async def get_pomodoro_stats():
    query = pomodoro_table.select().where(pomodoro_table.c.completed == True)
    sessions = await database.fetch_all(query)

    stats = {}
    total_time = 0
    for session in sessions:
        task_id = session["task_id"]
        duration = (session["end_time"] - session["start_time"]).total_seconds()
        stats[task_id] = stats.get(task_id, 0) + 1
        total_time += duration

    return {"completed_sessions": stats, "total_time_seconds": total_time}

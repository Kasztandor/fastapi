from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

app = FastAPI()

tasks = [
    {
        "id": 1,
        "title": "Nauka FastAPI",
        "description": "Przygotować przykładowe API z dokumentacją",
        "status": "TODO",
    }
]

pomodoro_sessions = []

class Task(BaseModel):
    title: str = Field(..., min_length=3, max_length=100)
    description: Optional[str] = Field(None, max_length=300)
    status: str = Field("TODO", pattern="^(TODO|IN_PROGRESS|DONE)$")

class PomodoroSession(BaseModel):
    task_id: int
    start_time: datetime
    end_time: Optional[datetime] = None
    completed: bool = False

@app.post("/tasks", status_code=201)
def create_task(task: Task):
    if any(t["title"] == task.title for t in tasks):
        raise HTTPException(status_code=400, detail="Task title must be unique.")

    new_task = {
        "id": len(tasks) + 1,
        "title": task.title,
        "description": task.description,
        "status": task.status,
    }
    tasks.append(new_task)
    return new_task

@app.get("/tasks", response_model=List[dict])
def get_tasks(status: Optional[str] = Query(None, pattern="^(TODO|IN_PROGRESS|DONE)$")):
    if status:
        return [task for task in tasks if task["status"] == status]
    return tasks

@app.get("/tasks/{task_id}")
def get_task(task_id: int):
    task = next((task for task in tasks if task["id"] == task_id), None)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    return task

@app.put("/tasks/{task_id}")
def update_task(task_id: int, updated_task: Task):
    task = next((task for task in tasks if task["id"] == task_id), None)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")

    if any(t["title"] == updated_task.title and t["id"] != task_id for t in tasks):
        raise HTTPException(status_code=400, detail="Task title must be unique.")

    task.update({
        "title": updated_task.title,
        "description": updated_task.description,
        "status": updated_task.status,
    })
    return task

@app.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int):
    global tasks
    task = next((task for task in tasks if task["id"] == task_id), None)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")

    tasks = [t for t in tasks if t["id"] != task_id]
    return

@app.post("/pomodoro", status_code=201)
def create_pomodoro(task_id: int):
    task = next((task for task in tasks if task["id"] == task_id), None)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")

    if any(session["task_id"] == task_id and not session["completed"] for session in pomodoro_sessions):
        raise HTTPException(status_code=400, detail="Active Pomodoro already exists for this task.")

    new_session = {
        "task_id": task_id,
        "start_time": datetime.now(),
        "end_time": None,
        "completed": False,
    }
    pomodoro_sessions.append(new_session)
    return new_session

@app.post("/pomodoro/{task_id}/stop")
def stop_pomodoro(task_id: int):
    session = next((session for session in pomodoro_sessions if session["task_id"] == task_id and not session["completed"]), None)
    if not session:
        raise HTTPException(status_code=404, detail="Active Pomodoro not found for this task.")

    session["end_time"] = datetime.now()
    session["completed"] = True
    return session

@app.get("/pomodoro/stats")
def get_pomodoro_stats():
    stats = {}
    total_time = 0
    for session in pomodoro_sessions:
        if session["completed"]:
            task_id = session["task_id"]
            duration = (session["end_time"] - session["start_time"]).total_seconds()
            stats[task_id] = stats.get(task_id, 0) + 1
            total_time += duration

    return {
        "completed_sessions": stats,
        "total_time_seconds": total_time,
    }

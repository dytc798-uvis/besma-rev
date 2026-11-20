from pathlib import Path
p=Path('/srv/besma/backend/app/main.py')
s=p.read_bytes()
line=b'\nfrom app.modules.home_weekly_todos import router as home_weekly_todos_router\napp.include_router(home_weekly_todos_router)\n'
if b'home_weekly_todos_router' not in s:
    p.write_bytes(s+line)

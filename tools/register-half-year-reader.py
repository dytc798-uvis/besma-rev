from pathlib import Path
p=Path('/srv/besma/backend/app/main.py')
s=p.read_bytes()
line=b'\nfrom app.modules.half_year_reviews.hq_reader import router as half_year_reader_router\napp.include_router(half_year_reader_router)\n'
if b'half_year_reader_router'not in s:p.write_bytes(s+line)

#!/bin/bash
cd /home/maximo/PROYECTOS/AlphaHunter
source .venv/bin/activate
uvicorn api.main:app --host 0.0.0.0 --port 8000

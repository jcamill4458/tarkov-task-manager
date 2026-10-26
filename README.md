# tarkov-task-manager

A simple desktop app for tracking & managing Escape from Tarkov tasks and viewing maps, all in one place.

## Features
- Track trader tasks: pick your tasks, and see the objectives and maps affiliated with them
- Interactive maps with place names, extract markers (PMC/Scav), and satellite views
- Individual task maps display objectives, and you can iterate objectives to completion
- Create your own pins on any individual tasks' map, which carry over to the larger map view

## Running it
1. Install Python
2. `pip install PySide6 requests platformdirs`
3. `python main.py`
   OR
build .exe with build file

First launch downloads data from tarkov.dev (needs internet), cache, progress and satellite tiles are saved in the local APPDATA folder

## Credits
- Task, map and extract data: [tarkov.dev](https://tarkov.dev)
- Map images: [tarkov-dev-svg-maps](https://github.com/the-hideout/tarkov-dev-svg-maps/) (CC BY-NC-SA 4.0, non-commercial use only)
- Satellite imagery: tiles from tarkov.dev (downloaded on demand)

Not affiliated with Battlestate Games.

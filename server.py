#!/bin/env python
from app import create_app, socketio
from app.db import connect_database

connect_database()
app = create_app()

if __name__ == '__man__':
    socketio.run(app)

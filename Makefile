.PHONY: all server_build client clean run-server run-client

all: server_build client

server_build:
	cd server && make

client:
	pip install -r requirements.txt || true

run-server:
	cd server && ./server

run-client:
	python3 client/GUI.py

clean:
	cd server && make clean || true

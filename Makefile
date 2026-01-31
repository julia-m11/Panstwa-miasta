all:
	$(MAKE) -C server all

run-server:
	cd server && ./server

run-client:
	python3 client/GUI.py

clean:
	$(MAKE) -C server clean

.PHONY: all run-server run-client clean

APXS ?= apxs

.PHONY: all test integration clean
all:
	$(APXS) -c -Wc,-Wall -Wc,-Wextra -Wc,-Werror mod_ja4.c ja4.c -lcrypto -lssl

test:
	python3 tests/test_ja4.py

integration: all
	python3 tests/test_apache.py

clean:
	rm -rf .libs *.la *.lo *.o *.slo tests/__pycache__

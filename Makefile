CXX ?= c++
CPPFLAGS := -Iinclude
CXXFLAGS := -std=c++17 -O3 -DNDEBUG -Wall -Wextra -Wpedantic
BIN := build
.PHONY: all test sanitize demo clean
all: $(BIN)/pipeline_exit $(BIN)/test_bloom $(BIN)/bloom_demo $(BIN)/study $(BIN)/early_exit
$(BIN):
	mkdir -p $(BIN)
$(BIN)/test_bloom: tests/test_bloom.cpp include/bloom.hpp | $(BIN)
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) $< -o $@
$(BIN)/bloom_demo: src/demo.cpp include/bloom.hpp | $(BIN)
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) $< -o $@
$(BIN)/study: src/study.cpp include/bloom.hpp | $(BIN)
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) $< -o $@
$(BIN)/early_exit: src/early_exit.cpp include/bloom.hpp | $(BIN)
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) $< -o $@
test: $(BIN)/test_bloom $(BIN)/bloom_demo
	./$(BIN)/test_bloom
	./$(BIN)/bloom_demo --what-breaks
sanitize: | $(BIN)
	$(CXX) $(CPPFLAGS) -std=c++17 -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer tests/test_bloom.cpp -o $(BIN)/test_sanitize
	./$(BIN)/test_sanitize
demo: $(BIN)/bloom_demo
	./$(BIN)/bloom_demo --what-breaks
clean:
	rm -rf $(BIN)

$(BIN)/pipeline_exit: src/pipeline_exit.cpp include/bloom.hpp | $(BIN)
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) $< -o $@

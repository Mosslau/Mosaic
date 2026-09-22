CC      = cc
CFLAGS  = -Wall -Wextra -std=c11 -pthread
TARGET  = tqdemo
OBJS    = main.o task_queue.o

$(TARGET): $(OBJS)
	$(CC) $(CFLAGS) $(OBJS) -o $(TARGET)

main.o: main.c task_queue.h
	$(CC) $(CFLAGS) -c main.c -o main.o

task_queue.o: task_queue.c task_queue.h
	$(CC) $(CFLAGS) -c task_queue.c -o task_queue.o

.PHONY: clean test
clean:
	rm -f $(OBJS) $(TARGET)

test: $(TARGET)
	./$(TARGET)

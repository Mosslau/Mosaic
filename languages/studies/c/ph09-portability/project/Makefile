CC      = cc
CFLAGS  = -Wall -Wextra -std=c11 -pthread
TARGET  = logdemo
OBJS    = main.o log.o

$(TARGET): $(OBJS)
	$(CC) $(CFLAGS) $(OBJS) -o $(TARGET)

main.o: main.c log.h
	$(CC) $(CFLAGS) -c main.c -o main.o

log.o: log.c log.h
	$(CC) $(CFLAGS) -c log.c -o log.o

.PHONY: clean test
clean:
	rm -f $(OBJS) $(TARGET) app.log app.log.*

test: $(TARGET)
	./$(TARGET)

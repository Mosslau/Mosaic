# project/Makefile —— 最小湖仓与编排平台（lakeplat）构建入口
# 验证环境：OpenJDK 17.0.18(Homebrew)
# 约定：所有构建产物只写到 /tmp，仓库工作区保持干净（无 target/、无 *.class）。
#
#   make        编译（等价于 javac -encoding UTF-8 -d /tmp/ph23-proj src/lakeplat/*.java）
#   make run    编译并运行端到端验收（期望末行 ALL PASS: 14/14）
#   make clean  删除 /tmp 下的构建产物

OUT ?= /tmp/ph23-proj
SRC := src/lakeplat
JAVAC ?= javac
JAVA ?= java

.PHONY: all run clean

all:
	$(JAVAC) -encoding UTF-8 -d $(OUT) $(SRC)/*.java

run: all
	$(JAVA) -cp $(OUT) lakeplat.LakePlatformDemo

clean:
	rm -rf $(OUT)

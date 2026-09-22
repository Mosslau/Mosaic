package main

import (
	"testing"
	"unsafe"
)

// ---- 反射加载器：JSON 来源 ----

func TestLoadFromJSON(t *testing.T) {
	var c Config
	err := LoadFromJSON(&c, `{"port":8080,"host":"0.0.0.0","debug":true,"timeout_ms":1.5,"tags":["a"]}`)
	if err != nil {
		t.Fatalf("LoadFromJSON: %v", err)
	}
	if c.Port != 8080 || c.Host != "0.0.0.0" || !c.Debug || c.TimeoutMS != 1.5 {
		t.Errorf("cfg 填充错误: %+v", c)
	}
	if len(c.Tags) != 0 {
		t.Errorf("cfg:\"-\" 字段不应被反射填充: %v", c.Tags)
	}
}

func TestLoadFromJSONMissingKeys(t *testing.T) {
	var c Config
	if err := LoadFromJSON(&c, `{"port":1}`); err != nil {
		t.Fatalf("缺 key 不应报错: %v", err)
	}
	if c.Port != 1 || c.Host != "" || c.Debug {
		t.Errorf("未提供的 key 应保持零值: %+v", c)
	}
}

func TestLoadFromJSONBadType(t *testing.T) {
	var c Config
	err := LoadFromJSON(&c, `{"port":"not-a-number"}`)
	if err == nil {
		t.Fatal("类型不匹配应报错")
	}
	if !contains(err.Error(), "port") {
		t.Errorf("错误信息应带字段名: %v", err)
	}
}

func TestLoadFromJSONOverflow(t *testing.T) {
	var c Config
	if err := LoadFromJSON(&c, `{"port":99999999999999999999}`); err == nil {
		t.Error("int 溢出应报错")
	}
}

// ---- 反射加载器：环境变量来源 ----

func TestLoadFromEnv(t *testing.T) {
	t.Setenv("APP_PORT", "9090")
	t.Setenv("APP_HOST", "127.0.0.1")
	t.Setenv("APP_DEBUG", "false")
	var c Config
	if err := LoadFromEnv(&c, "APP_"); err != nil {
		t.Fatalf("LoadFromEnv: %v", err)
	}
	if c.Port != 9090 || c.Host != "127.0.0.1" || c.Debug {
		t.Errorf("env 填充错误: %+v", c)
	}
}

func TestLoadFromEnvBadValue(t *testing.T) {
	t.Setenv("APP_PORT", "abc")
	var c Config
	if err := LoadFromEnv(&c, "APP_"); err == nil {
		t.Error("env 里非法数字应报错")
	}
}

// ---- unsafe 布局断言（go1.25.6 darwin/arm64 实测；架构不同可能不同）----

func TestUnsafeLayout(t *testing.T) {
	if unsafe.Sizeof(Point{}) != 24 {
		t.Errorf("Point Sizeof 应 24（padding），实测 %d", unsafe.Sizeof(Point{}))
	}
	if unsafe.Offsetof(Point{}.Y) != 8 {
		t.Errorf("Point.Y offset 应 8，实测 %d", unsafe.Offsetof(Point{}.Y))
	}
	if unsafe.Sizeof(Mixed{}) != 40 {
		t.Errorf("Mixed Sizeof 应 40，实测 %d", unsafe.Sizeof(Mixed{}))
	}
	if unsafe.Sizeof("") != 16 {
		t.Errorf("string 描述符应 16 字节，实测 %d", unsafe.Sizeof(""))
	}
	if unsafe.Sizeof([]int{}) != 24 {
		t.Errorf("slice 描述符应 24 字节，实测 %d", unsafe.Sizeof([]int{}))
	}
}

func contains(s, sub string) bool {
	for i := 0; i+len(sub) <= len(s); i++ {
		if s[i:i+len(sub)] == sub {
			return true
		}
	}
	return false
}

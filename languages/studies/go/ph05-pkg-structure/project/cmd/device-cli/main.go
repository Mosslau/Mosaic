// 来源：project/ —— 标准 Go 项目模板程序入口
// 一句话说明：cmd/device-cli 子命令 add/list/status/delete/config + -selfcheck，flag.NewFlagSet 解析。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：
//
//	cd project && go run ./cmd/device-cli -config config.example.json add -id D01 -name "温度传感器"
//	cd project && go run ./cmd/device-cli list
//	cd project && go run ./cmd/device-cli status -id D01 -state online
//	cd project && go run ./cmd/device-cli config
//	cd project && go run ./cmd/device-cli -selfcheck
//
// 验证状态：已验证（Go 1.22.2）
package main

import (
	"errors"
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"tenetlang/go/ph05-pkg-structure/project/internal/config"
	"tenetlang/go/ph05-pkg-structure/project/internal/device"
)

func main() {
	configPath := flag.String("config", "", "JSON 配置文件路径（缺省用内置默认配置）")
	selfCheck := flag.Bool("selfcheck", false, "运行内置自检")
	flag.Parse()
	args := flag.Args()

	if *selfCheck {
		if err := runSelfCheck(*configPath); err != nil {
			fmt.Fprintln(os.Stderr, "自检失败:", err)
			os.Exit(1)
		}
		fmt.Println("自检通过: 配置加载、设备增删改查、状态校验、文件持久化全部正常")
		return
	}
	if len(args) < 1 {
		usage()
		os.Exit(1)
	}

	store, cfg, err := openStore(*configPath)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	switch args[0] {
	case "add":
		cmdAdd(store, args[1:])
	case "list":
		cmdList(store)
	case "status":
		cmdStatus(store, args[1:])
	case "delete":
		cmdDelete(store, args[1:])
	case "config":
		cmdConfig(cfg)
	default:
		usage()
		os.Exit(1)
	}
}

// openStore 加载配置并打开设备存储——装配只发生在 main 层
func openStore(configPath string) (*device.Store, *config.Config, error) {
	cfg, err := config.Load(configPath)
	if err != nil {
		return nil, nil, err
	}
	store, err := device.NewStore(cfg.DataFile)
	if err != nil {
		return nil, nil, err
	}
	return store, cfg, nil
}

func cmdAdd(store *device.Store, args []string) {
	fs := flag.NewFlagSet("add", flag.ExitOnError)
	id := fs.String("id", "", "设备 ID")
	name := fs.String("name", "", "设备名称")
	typ := fs.String("type", "generic", "设备类型")
	st := fs.String("state", "offline", "初始状态: online/offline/fault")
	fs.Parse(args)
	if *id == "" || *name == "" {
		fs.Usage()
		os.Exit(1)
	}
	if err := store.Add(device.Device{ID: *id, Name: *name, Type: *typ, State: *st}); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	fmt.Printf("已添加设备 %s（%s）\n", *id, *name)
}

func cmdList(store *device.Store) {
	devices := store.List()
	if len(devices) == 0 {
		fmt.Println("暂无设备")
		return
	}
	for _, d := range devices {
		fmt.Printf("%s [%s] %s (%s)\n", d.ID, d.State, d.Name, d.Type)
	}
}

func cmdStatus(store *device.Store, args []string) {
	fs := flag.NewFlagSet("status", flag.ExitOnError)
	id := fs.String("id", "", "设备 ID")
	st := fs.String("state", "", "新状态: online/offline/fault")
	fs.Parse(args)
	if *id == "" || *st == "" {
		fs.Usage()
		os.Exit(1)
	}
	if err := store.SetState(*id, *st); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	fmt.Printf("设备 %s 状态已更新为 %s\n", *id, *st)
}

func cmdDelete(store *device.Store, args []string) {
	fs := flag.NewFlagSet("delete", flag.ExitOnError)
	id := fs.String("id", "", "设备 ID")
	fs.Parse(args)
	if *id == "" {
		fs.Usage()
		os.Exit(1)
	}
	if err := store.Delete(*id); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	fmt.Printf("已删除设备 %s\n", *id)
}

func cmdConfig(cfg *config.Config) {
	fmt.Printf("端口: %d\n数据目录: %s\n数据文件: %s\n日志级别: %s\n", cfg.Port, cfg.DataDir, cfg.DataFile, cfg.LogLevel)
}

// runSelfCheck 跑通全链路：配置加载、增删改查、非法输入拒绝、文件持久化重载
func runSelfCheck(configPath string) error {
	if _, err := config.Load(configPath); err != nil {
		return fmt.Errorf("config.Load: %w", err)
	}
	dir, err := os.MkdirTemp("", "device-cli-selfcheck-*")
	if err != nil {
		return err
	}
	defer os.RemoveAll(dir)
	dataFile := filepath.Join(dir, "devices.json")

	store, err := device.NewStore(dataFile)
	if err != nil {
		return err
	}
	if err := store.Add(device.Device{ID: "D01", Name: "温度传感器", Type: "sensor"}); err != nil {
		return fmt.Errorf("Add D01: %w", err)
	}
	if err := store.Add(device.Device{ID: "D02", Name: "运行速度传感器", Type: "sensor"}); err != nil {
		return fmt.Errorf("Add D02: %w", err)
	}
	if err := store.SetState("D01", "online"); err != nil {
		return fmt.Errorf("SetState: %w", err)
	}
	if err := store.SetState("D01", "nonsense"); err == nil {
		return fmt.Errorf("非法状态应被拒绝")
	}
	if err := store.Delete("D02"); err != nil {
		return fmt.Errorf("Delete: %w", err)
	}
	if err := store.Delete("D02"); !errors.Is(err, device.ErrNotFound) {
		return fmt.Errorf("重复删除期望 ErrNotFound，得到 %v", err)
	}
	// 文件持久化：重开 Store 后 D01（含状态）仍在
	reopened, err := device.NewStore(dataFile)
	if err != nil {
		return err
	}
	if got := len(reopened.List()); got != 1 {
		return fmt.Errorf("持久化后设备数期望 1，得到 %d", got)
	}
	if got := reopened.List()[0].State; got != "online" {
		return fmt.Errorf("持久化后状态期望 online，得到 %q", got)
	}
	return nil
}

func usage() {
	fmt.Fprintln(os.Stderr, "用法: device-cli <add|list|status|delete|config> [flags...]")
}

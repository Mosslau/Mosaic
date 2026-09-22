package sharedlib

import "testing"

func TestGreet(t *testing.T) {
	got := Greet("workspace")
	want := "Hello from sharedlib, workspace!"
	if got != want {
		t.Fatalf("Greet() = %q, want %q", got, want)
	}
}

# -*- coding: utf-8 -*-
extends Control
## 简易折线图：显示 n / species / T（归一化）随时间变化。

var series := {}          # name -> Array[float]
var colors := {}          # name -> Color
var max_points := 400
var title := "曲线"

func setup(names: Array, cols: Array) -> void:
	for i in range(names.size()):
		series[names[i]] = []
		colors[names[i]] = cols[i]

func push(name: String, value: float) -> void:
	if not series.has(name):
		series[name] = []
	var arr: Array = series[name]
	arr.append(value)
	if arr.size() > max_points:
		arr.pop_front()

func clear_all() -> void:
	for k in series.keys():
		series[k] = []
	queue_redraw()

func _draw() -> void:
	var r := Rect2(Vector2.ZERO, size)
	draw_rect(r, Color(0.07, 0.08, 0.10))
	draw_rect(r, Color(0.30, 0.33, 0.38), false, 1.0)
	var t_font := ThemeDB.fallback_font
	var fsize := 12
	for gi in range(1, 4):
		var y := size.y * gi / 4.0
		draw_line(Vector2(0, y), Vector2(size.x, y), Color(0.20, 0.22, 0.26), 1.0)
	var i := 0
	for name in series.keys():
		var arr: Array = series[name]
		if arr.size() < 2:
			i += 1
			continue
		var mx := 0.0
		for v in arr:
			mx = max(mx, float(v))
		if mx <= 0.0:
			mx = 1.0
		var pts := PackedVector2Array()
		for k in range(arr.size()):
			var x := size.x * float(k) / float(max_points - 1)
			var y := size.y - size.y * float(arr[k]) / mx
			pts.append(Vector2(x, y))
		draw_polyline(pts, colors.get(name, Color.WHITE), 1.5)
		draw_string(t_font, Vector2(6, 14 + i * 14), "%s max=%.1f" % [name, mx],
				HORIZONTAL_ALIGNMENT_LEFT, -1, fsize, colors.get(name, Color.WHITE))
		i += 1

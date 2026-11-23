# -*- coding: utf-8 -*-
extends Node2D
## ChemLab：九元素化学实验场地。
## 左侧：世界视图（每格 1 像素，按物质同色，骨架占 k 格）
## 右侧：参数面板（世界/物理/温度/反应/投料/注入/运行/存档）
## 物理与反应全部由 scripts/sim.gd 计算，反应产物来自 Python 内核侧车。

const KernelClientScript = preload("res://scripts/kernel_client.gd")
const ChemSimScript = preload("res://scripts/sim.gd")
const ChartScript = preload("res://scripts/chart.gd")

const ZOOM_MIN := 1.0
const ZOOM_MAX := 32.0

var client
var sim
var world_img: Image
var world_tex: ImageTexture
var sprite: Sprite2D
var cam: Camera2D
var chart
var zoom := 5.0

var running := false
var speed := 20.0
var acc := 0.0
var tick_done := 0

var ui: Control
var hud: Label
var status_label: Label
var hint_label: Label
var chart_ticks := 0
var tick_label: Label

var color_cache := {}
var place_formula := "CKF2"
var place_mode := 0   # 0=放置 1=删除
var last_cell := Vector2i(-1, -1)

var W_edit: SpinBox
var H_edit: SpinBox
var seed_edit: SpinBox
var formula_edit: LineEdit
var count_edit: SpinBox
var preset_opt: OptionButton
var _shot_mode := false
var _selftest := false
var _selftest_ticks := 0
var _panel_node: PanelContainer
var panel_scroll: ScrollContainer
var panel: PanelContainer
var _frames := 0
var elem_checks := {}

func _ready() -> void:
	world_img = Image.create(200, 140, false, Image.FORMAT_RGBA8)
	world_img.fill(Color(0.06, 0.07, 0.09))
	world_tex = ImageTexture.create_from_image(world_img)
	sprite = Sprite2D.new()
	sprite.texture = world_tex
	sprite.centered = true
	add_child(sprite)
	cam = Camera2D.new()
	add_child(cam)
	cam.make_current()
	sprite.scale = Vector2(zoom, zoom)
	cam.position = Vector2.ZERO

	client = KernelClientScript.new()
	client.kernel_ready.connect(_on_kernel_ready)
	add_child(client)

	sim = ChemSimScript.new()
	sim.setup(200, 140, client)
	sim.reset()

	_build_ui()
	_refresh_image()
	_shot_mode = "--screenshot" in OS.get_cmdline_args()
	_selftest = "--selftest" in OS.get_cmdline_args()
	_status("等待内核…" if not client.is_kernel_connected() else "就绪")

func _on_kernel_ready(ok: bool) -> void:
	if ok:
		_status("内核已连接（127.0.0.1:8765）")
		call_deferred("_auto_demo")
	else:
		_status("内核未连接：请先运行 run_lab.bat（会启动 Python 服务）")

# ---------------- UI ----------------
func _build_ui() -> void:
	var layer := CanvasLayer.new()
	add_child(layer)
	ui = Control.new()
	ui.set_anchors_preset(Control.PRESET_FULL_RECT)
	ui.mouse_filter = Control.MOUSE_FILTER_IGNORE
	layer.add_child(ui)
	var sysf := SystemFont.new()
	sysf.font_names = PackedStringArray(["Microsoft YaHei", "SimHei", "Noto Sans CJK SC"])
	var th := Theme.new()
	th.default_font = sysf
	th.default_font_size = 13
	ui.theme = th

	ui.set_anchors_preset(Control.PRESET_FULL_RECT)
	panel = PanelContainer.new()
	ui.add_child(panel)
	_panel_node = panel
	get_tree().root.size_changed.connect(_layout_ui)
	_layout_ui()

	var scroll := ScrollContainer.new()
	panel_scroll = scroll
	panel.add_child(scroll)
	var v := VBoxContainer.new()
	v.custom_minimum_size = Vector2(372, 0)
	v.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(v)

	var title := Label.new()
	title.text = "九元素化学实验场 ChemLab"
	title.add_theme_font_size_override("font_size", 18)
	v.add_child(title)
	var sub := Label.new()
	sub.text = "规则：连续重力 + 三素非对称力 + 骨架占格 + 温度门控 resolve 反应"
	sub.add_theme_font_size_override("font_size", 11)
	sub.add_theme_color_override("font_color", Color(0.65, 0.68, 0.72))
	v.add_child(sub)

	# 运行控制
	_section(v, "运行")
	var row := HBoxContainer.new()
	v.add_child(row)
	_btn(row, "▶ 播放", _toggle_play)
	_btn(row, "❚❚ 暂停", func(): running = false)
	_btn(row, "单步", func(): _do_tick(1))
	_btn(row, "重置", _reset_world)
	tick_label = Label.new()
	tick_label.text = "tick 0"
	v.add_child(tick_label)
	_slider(v, "speed", "速度（拍/秒）", 1, 120, 1, speed, func(x): speed = x)

	# 世界
	_section(v, "世界")
	var row2 := HBoxContainer.new()
	v.add_child(row2)
	row2.add_child(_mk_label("宽 W"))
	W_edit = _spin(row2, 60, 800, 10, 200, 1)
	row2.add_child(_mk_label("高 H"))
	H_edit = _spin(row2, 40, 600, 10, 140, 1)
	var row3 := HBoxContainer.new()
	v.add_child(row3)
	row3.add_child(_mk_label("随机种子"))
	seed_edit = _spin(row3, 1, 999999999, 1, 20261120, 0, 110)
	_btn(row3, "应用世界尺寸", func():
		var w := int(W_edit.value)
		var h := int(H_edit.value)
		_rebuild_world(w, h)
	)
	var wall_row := HBoxContainer.new()
	v.add_child(wall_row)
	var wall_chk := CheckButton.new()
	wall_chk.text = "硬墙边界（四壁封死，不能穿越）"
	wall_chk.button_pressed = bool(sim.p.get("hard_walls", true))
	wall_chk.tooltip_text = "开启=硬墙（越界被挡住）；关闭=环面（从一边出去另一边进来）"
	wall_chk.toggled.connect(func(on: bool):
		sim.p["hard_walls"] = on
		_status("边界 = %s" % ("硬墙" if on else "环面"))
	)
	wall_row.add_child(wall_chk)

	# 投料
	_section(v, "投料（预设 / 自由勾选 / 自定义清单）")
	preset_opt = OptionButton.new()
	preset_opt.add_item("T91 主体 A/食物 B/C：XK2F4 + XKF + KF3", 0)
	preset_opt.add_item("T91 主体 A/食物 B/C：XP2F4 + XPF + PF3", 1)
	preset_opt.add_item("T91 主体 A/食物 B/C：O2AF4 + OAF + OF3", 2)
	preset_opt.add_item("T91 主体 A/食物 B/C：O2WF4 + OWF + OF3", 3)
	preset_opt.add_item("T88 群系 B3_OFL（O,F,L）", 4)
	preset_opt.add_item("T88 群系 B3_OXC（O,X,C）", 5)
	preset_opt.add_item("T88 群系 B4_OXKF（O,X,K,F）", 6)
	preset_opt.add_item("T88 群系 B5_OXKAF（O,X,K,A,F）", 7)
	preset_opt.add_item("T88 群系 B6_OXCKAF", 8)
	preset_opt.add_item("T88 群系 B9_all9（九元素）", 9)
	preset_opt.add_item("自由投料（按元素勾选）", 10)
	v.add_child(preset_opt)
	var row4 := HBoxContainer.new()
	v.add_child(row4)
	row4.add_child(_mk_label("预设分子数"))
	feed_n_edit = _spin(row4, 50, 20000, 50, 2500, 0, 90)
	_btn(row4, "应用预设（先清空）", _apply_preset)

	var elem_row := GridContainer.new()
	elem_row.columns = 5
	v.add_child(elem_row)
	for e in ["O", "X", "C", "P", "W", "L", "K", "A", "F"]:
		var cb := CheckBox.new()
		cb.text = e
		cb.button_pressed = true
		elem_checks[e] = cb
		elem_row.add_child(cb)
	var row4b := HBoxContainer.new()
	v.add_child(row4b)
	_btn(row4b, "按勾选元素配平投放", func(): _apply_checked(int(feed_n_edit.value)))

	# 自定义投料清单：可精确指定"哪种物质、多少个"
	var feed_title := Label.new()
	feed_title.text = "自定义投料清单（可混合任意物种）"
	feed_title.add_theme_font_size_override("font_size", 12)
	feed_title.add_theme_color_override("font_color", Color(0.75, 0.85, 1.0))
	v.add_child(feed_title)
	var rowf := HBoxContainer.new()
	v.add_child(rowf)
	feed_formula_edit = LineEdit.new()
	feed_formula_edit.text = "CKF2"
	feed_formula_edit.placeholder_text = "分子式（如 XK2F4 / CKF2）"
	feed_formula_edit.custom_minimum_size = Vector2(150, 0)
	feed_formula_edit.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	rowf.add_child(feed_formula_edit)
	feed_count_edit = _spin(rowf, 1, 5000, 1, 100, 0, 78)
	_btn(rowf, "加入清单", _feed_add)
	feed_list = ItemList.new()
	feed_list.custom_minimum_size = Vector2(352, 96)
	feed_list.select_mode = ItemList.SELECT_MULTI
	v.add_child(feed_list)
	var rowf2 := HBoxContainer.new()
	v.add_child(rowf2)
	_btn(rowf2, "删除选中", _feed_remove_selected)
	_btn(rowf2, "清空清单", _feed_clear)
	_btn(rowf2, "应用清单（叠加）", func(): _feed_apply(false))
	_btn(rowf2, "应用清单（先清空）", func(): _feed_apply(true))

	# 物理
	_section(v, "物理（三素力 + 重力）")
	_slider(v, "gravity_G", "重力 G", 0, 1.0, 0.01, sim.p["gravity_G"], func(x): pass,
		"每拍每单位质量增加的向下位移（格）。质量 3 → 约 0.9 格/拍；0 = 关重力。硬墙下会在底部堆积。")
	_slider(v, "KA", "吸引力 KA", 0, 6.0, 0.05, sim.p["KA"], func(x): pass,
		"聚素吸引强度上限：两个 A=3 分子贴邻时的最大吸引力（默认 2.5，与内核短键 κ0 同量级）。")
	_slider(v, "KR", "排斥力 KR", 0, 3.0, 0.05, sim.p["KR"], func(x): pass,
		"动素排斥强度上限：两个 D=3 分子贴邻时的最大排斥力（默认 0.5）。KA:KR 越大，同种越容易聚。")
	_slider(v, "force_r", "作用力半径", 1, 6, 1, sim.p["force_r"], func(x): pass,
		"力按切比雪夫距离向外衰减的半径（格）。半径 3 = 3 格内的邻居都参与受力。")
	_slider(v, "lock_w", "粘附锁阈值", 0, 4.0, 0.05, sim.p["lock_w"], func(x): pass,
		"双方净力 w 都 ≥ 该值时，两个相邻分子被'粘附锁'锁住（只锁相对位置，不是化学键）。")
	_slider(v, "lock_r", "锁断裂距离", 1, 5, 1, sim.p["lock_r"], func(x): pass,
		"被锁住的伙伴距离超过该值时锁失效（默认 2 格）。")
	var rigid_row := HBoxContainer.new()
	v.add_child(rigid_row)
	var rigid_chk := CheckButton.new()
	rigid_chk.text = "锁团整体下落（刚体：锁住的分子簇一起受重力）"
	rigid_chk.button_pressed = bool(sim.p.get("lock_rigid_fall", true))
	rigid_chk.toggled.connect(func(on: bool):
		sim.p["lock_rigid_fall"] = on
		_status("锁团刚体下落 = %s" % ("开" if on else "关"))
	)
	rigid_row.add_child(rigid_chk)
	_slider(v, "mob_gas", "气态迁移率", 0, 1.5, 0.05, sim.p["mob_gas"], func(x): pass,
		"物态=气 的分子响应合力的概率倍率（1.0 = 完全响应）。")
	_slider(v, "mob_liq", "液态迁移率", 0, 1.5, 0.05, sim.p["mob_liq"], func(x): pass,
		"物态=液 的迁移率（默认 0.6，比气态难动）。")
	_slider(v, "mob_solid", "固态迁移率", 0, 1.5, 0.05, sim.p["mob_solid"], func(x): pass,
		"物态=固 的迁移率（默认 0.25，最重最黏）。")

	# 温度
	_section(v, "温度（分子热值 + 环境温度场）")
	var hw_row := HBoxContainer.new()
	v.add_child(hw_row)
	hw_row.add_child(_mk_label("热值权重 C / L / F："))
	var wC := _spin(hw_row, -4, 4, 0.5, float(sim.p["heat_w"]["C"]), 1, 62)
	var wL := _spin(hw_row, -4, 4, 0.5, float(sim.p["heat_w"]["L"]), 1, 62)
	var wF := _spin(hw_row, -4, 4, 0.5, float(sim.p["heat_w"]["F"]), 1, 62)
	var hw_btn_row := HBoxContainer.new()
	v.add_child(hw_btn_row)
	_btn(hw_btn_row, "应用热值权重（重算所有分子 heat）", func():
		sim.p["heat_w"] = {"C": float(wC.value), "L": float(wL.value), "F": float(wF.value)}
		sim.recompute_heat()
		_status("热值权重 = C %.1f / L %.1f / F %.1f（heat = Σ w·n，可为负）" % [wC.value, wL.value, wF.value])
	)
	v.add_child(_mk_label("heat = wC·n_C + wL·n_L + wF·n_F；默认 C=-1（冰）、L=1（电）、F=2（焰）。改数值后点“应用热值权重”，所有分子热值立即重算。"))
	_slider(v, "T0", "初始温度 T0", 0, 1200, 10, sim.p["T0"], func(x): pass,
		"第 0 拍的环境温度；会按 exp 曲线降到 T_end。")
	_slider(v, "T_end", "终温 T_end", 0, 400, 1, sim.p["T_end"], func(x): pass,
		"降温目标温度；恒温平台开启时，降到它之后保持不变。")
	_slider(v, "cool_ticks", "降温拍数", 10, 3000, 10, sim.p["cool_ticks"], func(x): pass,
		"从 T0 按 exp(-6t/ct) 降到 T_end 所需的拍数；之后进入恒温平台。")
	_slider(v, "env_coupling", "环境耦合强度", 0.1, 20, 0.1, sim.p["env_coupling"], func(x): pass,
		"局部温度 = (周围分子平均热值 + 环境耦合×T_env) / (n + 环境耦合)。越大越接近环境温度。")
	var plat_row := HBoxContainer.new()
	v.add_child(plat_row)
	var plat_chk := CheckButton.new()
	plat_chk.text = "降温后恒温平台（关闭则继续降向 0）"
	plat_chk.button_pressed = bool(sim.p.get("plateau", true))
	plat_chk.toggled.connect(func(on: bool):
		sim.p["plateau"] = on
		_status("恒温平台 = %s" % ("开" if on else "关"))
	)
	plat_row.add_child(plat_chk)

	# 反应
	_section(v, "反应（resolve 完全 / 不完全）")
	_slider(v, "p_react", "反应概率/接触", 0, 1.0, 0.01, sim.p["p_react"], func(x): pass,
		"每个相邻对每拍触发一次 resolve 的概率（0~1；1.0 = 只要温度和 cap 满足，每次接触必反应）。")
	_slider(v, "react_margin", "温度门槛余量", 0, 20, 0.5, sim.p["react_margin"], func(x): pass,
		"触发反应要求 局部温度 ≥ c_A+c_B+余量；余量越大越难反应。")
	_slider(v, "cap", "反应原子上限 cap", 4, 80, 1, sim.p["cap"], func(x): pass,
		"两个反应物原子数之和超过它就不反应（默认 36，防止大分子爆炸式合并）。")
	_slider(v, "max_react", "每拍最多反应对", 0, 2000, 10, sim.max_react_per_tick, func(x): pass,
		"每拍最多发起的 resolve 请求数（防止一次卡死；600 适合 200×140）。")

	# 注入
	_section(v, "点击注入 / 删除")
	var row5 := HBoxContainer.new()
	v.add_child(row5)
	formula_edit = LineEdit.new()
	formula_edit.text = "CKF2"
	formula_edit.custom_minimum_size = Vector2(120, 0)
	row5.add_child(formula_edit)
	_btn(row5, "查询", func(): _query_formula())
	count_edit = _spin(row5, 1, 500, 1, 1, 0, 60)
	var row6 := HBoxContainer.new()
	v.add_child(row6)
	_btn(row6, "放置模式", func(): place_mode = 0; place_formula = formula_edit.text.strip_edges(); _status("点击世界 = 放置 %s" % place_formula))
	_btn(row6, "删除模式", func(): place_mode = 1; _status("点击世界 = 删除该格分子"))
	var row6b := HBoxContainer.new()
	v.add_child(row6b)
	_btn(row6b, "清空所有分子", func(): _reset_world(); _status("已清空分子"))
	_btn(row6b, "随机撒 200 个当前式", func():
		var f := formula_edit.text.strip_edges()
		var arr: Array = [{"formula": f, "count": 200}]
		var n: int = sim.add_feed(arr)
		_refresh_image()
		_status("撒入 %s × %d" % [f, n])
	)
	info_label = Label.new()
	info_label.add_theme_font_size_override("font_size", 11)
	info_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	v.add_child(info_label)

	# 存档
	_section(v, "存档 / 导出")
	var row7 := HBoxContainer.new()
	v.add_child(row7)
	_btn(row7, "保存状态", _save_state)
	_btn(row7, "读取状态", _load_state)
	_btn(row7, "导出 CSV", _export_csv)
	var row8 := HBoxContainer.new()
	v.add_child(row8)
	_btn(row8, "保存截图", _screenshot)

	# 曲线
	var chart_title := Label.new()
	chart_title.text = "曲线（n 分子 / 种数 / 环境温度）"
	v.add_child(chart_title)
	chart = ChartScript.new()
	chart.custom_minimum_size = Vector2(360, 140)
	chart.setup(["n", "species", "T_env"], [Color(0.4, 0.9, 1.0), Color(1.0, 0.85, 0.3), Color(1.0, 0.4, 0.4)])
	v.add_child(chart)

	hint_label = Label.new()
	hint_label.text = "空格=播放/暂停  R=重置  +/-=缩放  右键拖动=平移  滚轮=缩放"
	hint_label.add_theme_font_size_override("font_size", 10)
	hint_label.add_theme_color_override("font_color", Color(0.6, 0.63, 0.68))
	v.add_child(hint_label)

	# 左下 HUD
	hud = Label.new()
	hud.position = Vector2(10, 8)
	hud.add_theme_font_size_override("font_size", 14)
	ui.add_child(hud)
	status_label = Label.new()
	status_label.position = Vector2(10, 34)
	status_label.add_theme_font_size_override("font_size", 11)
	status_label.add_theme_color_override("font_color", Color(0.7, 0.75, 0.8))
	ui.add_child(status_label)

func _section(parent: Node, text: String) -> void:
	var sep := HSeparator.new()
	parent.add_child(sep)
	var l := Label.new()
	l.text = "── %s ──" % text
	l.add_theme_color_override("font_color", Color(0.55, 0.8, 1.0))
	parent.add_child(l)

func _mk_label(t: String) -> Label:
	var l := Label.new()
	l.text = t
	return l

func _btn(parent: Node, text: String, cb: Callable) -> Button:
	var b := Button.new()
	b.text = text
	b.pressed.connect(cb)
	parent.add_child(b)
	return b

func _spin(parent: Node, mn: float, mx: float, step: float, val: float, digits: int, width: int = 80) -> SpinBox:
	var s := SpinBox.new()
	s.min_value = mn
	s.max_value = mx
	s.step = step
	s.value = val
	if digits > 0:
		s.custom_minimum_size = Vector2(width, 0)
	parent.add_child(s)
	return s

func _fmt(v: float, step: float) -> String:
	if step >= 1.0:
		return "%d" % int(round(v))
	if step >= 0.1:
		return "%.2f" % v
	return "%.3f" % v

func _slider(parent: Node, key: String, label: String, mn: float, mx: float, step: float, val: float, setter: Callable, hint: String = "") -> void:
	var vb := VBoxContainer.new()
	parent.add_child(vb)
	var l := Label.new()
	l.text = "%s：%s" % [label, _fmt(val, step)]
	l.add_theme_font_size_override("font_size", 12)
	vb.add_child(l)
	if hint != "":
		l.tooltip_text = hint
		l.mouse_filter = Control.MOUSE_FILTER_STOP
	var row := HBoxContainer.new()
	vb.add_child(row)
	var sl := HSlider.new()
	sl.min_value = mn
	sl.max_value = mx
	sl.step = step
	sl.value = val
	sl.custom_minimum_size = Vector2(250, 18)
	sl.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	if hint != "":
		sl.tooltip_text = hint
	var sp := SpinBox.new()
	sp.min_value = mn
	sp.max_value = mx
	sp.step = step
	sp.value = val
	sp.custom_minimum_size = Vector2(92, 0)
	sp.select_all_on_focus = true
	if hint != "":
		sp.tooltip_text = hint
	var apply := func(v: float):
		sl.set_value_no_signal(v)
		sp.set_value_no_signal(v)
		l.text = "%s：%s" % [label, _fmt(v, step)]
		if key == "speed":
			speed = v
		elif key == "max_react":
			sim.max_react_per_tick = int(round(v))
		else:
			sim.p[key] = float(v)
		setter.call(v)
	sl.value_changed.connect(apply)
	sp.value_changed.connect(apply)
	row.add_child(sl)
	row.add_child(sp)
	var help := Label.new()
	help.text = hint
	help.add_theme_font_size_override("font_size", 10)
	help.add_theme_color_override("font_color", Color(0.55, 0.58, 0.63))
	help.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	help.visible = hint != ""
	vb.add_child(help)

var feed_n_edit: SpinBox
var info_label: Label
var feed_list: ItemList
var feed_formula_edit: LineEdit
var feed_count_edit: SpinBox
var feed_items: Array = []

func _refresh_feed_list() -> void:
	if feed_list == null:
		return
	feed_list.clear()
	for it in feed_items:
		var d: Dictionary = sim.info(String(it["formula"]))
		var nat := int(d.get("natoms", 0)) if not d.is_empty() else -1
		feed_list.add_item("%-16s × %-5d   （%d 原子）" % [it["formula"], int(it["count"]), nat])

func _feed_add() -> void:
	var f := feed_formula_edit.text.strip_edges()
	if f == "":
		return
	var d: Dictionary = sim.info(f)
	if d.is_empty():
		_status("未知分子式：%s（先在“点击注入/查询”里试一下）" % f)
		return
	var n := int(feed_count_edit.value)
	if n <= 0:
		return
	feed_items.append({"formula": f, "count": n})
	_refresh_feed_list()
	_status("已加入 %s × %d" % [f, n])

func _feed_remove_selected() -> void:
	var idxs: Array = []
	for i in feed_list.get_selected_items():
		idxs.append(int(i))
	idxs.sort()
	idxs.reverse()
	for i in idxs:
		if i < feed_items.size():
			feed_items.remove_at(i)
	_refresh_feed_list()

func _feed_clear() -> void:
	feed_items.clear()
	_refresh_feed_list()
	_status("投料清单已清空")

func _feed_apply(clear_world: bool) -> void:
	if feed_items.is_empty():
		_status("投料清单为空：先在上面的输入框里“加入清单”")
		return
	if clear_world:
		sim.reset()
		tick_done = 0
		chart.clear_all()
	var placed: int = sim.add_feed(feed_items)
	_refresh_image()
	_status("清单投放 %d 个分子（%d 条投料）" % [placed, feed_items.size()])

func _layout_ui() -> void:
	var vs := get_viewport_rect().size
	if sim and sim.W > 0:
		var zx := (vs.x - 420.0) / float(sim.W)
		var zy := (vs.y - 70.0) / float(sim.H)
		zoom = clamp(min(zx, zy), ZOOM_MIN, ZOOM_MAX)
		if sprite:
			sprite.scale = Vector2(zoom, zoom)
		if cam:
			cam.position = Vector2(200.0 / zoom, 0)
	if _panel_node:
		_panel_node.position = Vector2(max(200.0, vs.x - 400.0), 8)
		_panel_node.set_deferred("size", Vector2(392, max(200.0, vs.y - 16.0)))

func _status(t: String) -> void:
	if status_label:
		status_label.text = t

# ---------------- 世界 ----------------
func _rebuild_world(w: int, h: int) -> void:
	sim.setup(w, h, client)
	world_img = Image.create(w, h, false, Image.FORMAT_RGBA8)
	world_img.fill(Color(0.06, 0.07, 0.09))
	world_tex = ImageTexture.create_from_image(world_img)
	sprite.texture = world_tex
	sprite.scale = Vector2(zoom, zoom)
	cam.position = Vector2.ZERO
	_refresh_image()
	_status("世界已重建 %dx%d" % [w, h])

func _reset_world() -> void:
	sim.reset()
	_refresh_image()
	tick_done = 0
	chart.clear_all()

func _color(f: String) -> Color:
	if color_cache.has(f):
		return color_cache[f]
	var h := float(f.hash() % 997) / 997.0
	var c := Color.from_hsv(h, 0.62, 0.95)
	color_cache[f] = c
	return c

func _refresh_image() -> void:
	if world_img == null:
		return
	if world_img.get_width() != sim.W or world_img.get_height() != sim.H:
		world_img = Image.create(sim.W, sim.H, false, Image.FORMAT_RGBA8)
	world_img.fill(Color(0.06, 0.07, 0.09))
	for m in sim.mols:
		if m["dead"]:
			continue
		var col := _color(String(m["f"]))
		for c in m["cells"]:
			var x := int(c.y)
			var y := int(c.x)
			if x >= 0 and x < sim.W and y >= 0 and y < sim.H:
				world_img.set_pixel(x, y, col)
	world_tex.update(world_img)

func _process(delta: float) -> void:
	# 异步结果回收
	if client:
		client.poll()
	if running:
		acc += delta * speed
		var guard: int = 0
		while acc >= 1.0 and guard < 200:
			guard += 1
			_do_tick(1)
			acc -= 1.0
	_refresh_image()
	_update_hud()
	_frames += 1
	if _selftest and _frames == 20:
		if "--lock1" in OS.get_cmdline_args():
			sim.p["lock_r"] = 1
			sim.p["lock_rigid_fall"] = not ("--no-rigid" in OS.get_cmdline_args())
			_status("自检：lock_r=1, rigid=%s" % str(sim.p["lock_rigid_fall"]))
	if _selftest and _frames > 20 and _selftest_ticks < 240:
		_do_tick(2)
		_selftest_ticks += 2
		if _selftest_ticks >= 240:
			print("[selftest] tick=%d N=%d species=%d complete=%d incomplete=%d none=%d drops=%d joins=%d pend=%d T=%.1f" % [
				tick_done, int(sim.stats["n"]), int(sim.stats["species"]),
				int(sim.stats["complete"]), int(sim.stats["incomplete"]), int(sim.stats["none"]),
				int(sim.stats["drops"]), int(sim.stats["joins"]), client.pending_count(),
				float(sim.stats["T_env"])])
			print("[selftest] rho=%.4f" % sim.rho())
			var oob := 0
			var maxrow := -1
			for m in sim.mols:
				if m["dead"]:
					continue
				for c in m["cells"]:
					maxrow = max(maxrow, int(c.x))
					if c.x < 0 or c.x >= sim.H or c.y < 0 or c.y >= sim.W:
						oob += 1
			var n_high := 0
			var n_low := 0
			var row_sum := 0.0
			var n_alive := 0
			for m in sim.mols:
				if m["dead"]:
					continue
				n_alive += 1
				row_sum += float(m["anchor"].x)
				if int(m["anchor"].x) < sim.H - 30:
					n_high += 1
				if int(m["anchor"].x) >= sim.H - 10:
					n_low += 1
			print("[selftest] rows: mean=%.1f H=%d high(row<%d)=%d low(row>=%d)=%d lock_r=%s rigid=%s" % [
				(row_sum / max(1, n_alive)), sim.H, sim.H - 30, n_high, sim.H - 10, n_low,
				str(sim.p["lock_r"]), str(sim.p.get("lock_rigid_fall", true))])
			print("[selftest] hard_walls=%s oob_cells=%d max_row=%d H=%d (max_row 应 <= H-1)" % [
				str(sim.p.get("hard_walls", true)), oob, maxrow, sim.H])
			get_tree().quit()
			return
	if _shot_mode and _frames >= 20 and _frames < 60:
		_do_tick(2)
	if _shot_mode and _frames == 60:
		var img := get_viewport().get_texture().get_image()
		if img == null:
			print("[shot] get_image() 返回 null（headless 模式不支持截图）")
			get_tree().quit()
		else:
			img.save_png("res://screenshot_check.png")
			_status("已保存 screenshot_check.png")
		if panel_scroll:
			panel_scroll.scroll_vertical = 430
	if _shot_mode and _frames == 64:
		var img2 := get_viewport().get_texture().get_image()
		if img2 != null:
			img2.save_png("res://screenshot_bottom.png")
		get_tree().quit()
	if running and tick_done % 3 == 0:
		chart_ticks += 1
		chart.push("n", float(sim.stats["n"]))
		chart.push("species", float(sim.stats["species"]))
		chart.push("T_env", float(sim.stats["T_env"]))
		chart.queue_redraw()

func _do_tick(n: int) -> void:
	for i in range(n):
		sim.step()
		tick_done += 1

func _update_hud() -> void:
	if hud == null:
		return
	var s = sim.stats
	hud.text = "tick=%d  N=%d  种=%d  |  complete=%d  incomplete=%d  none=%d  drops=%d  并入=%d  |  T_env=%.1f  ρ=%.3f  pending=%d" % [
		tick_done, int(s["n"]), int(s["species"]),
		int(s["complete"]), int(s["incomplete"]), int(s["none"]),
		int(s["drops"]), int(s["joins"]),
		float(s["T_env"]), sim.rho(), client.pending_count() if client else 0]
	if tick_label:
		tick_label.text = "tick %d" % tick_done

func _auto_demo() -> void:
	if sim.stats["n"] > 0:
		return
	preset_opt.selected = 0
	feed_n_edit.value = 400
	_apply_preset()
	_status("已加载 T91 预设：主体 XK2F4 + 食物 XKF/KF3（按 ▶ 播放）")

# ---------------- 输入 ----------------
func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		var mb := event as InputEventMouseButton
		if mb.button_index == MOUSE_BUTTON_WHEEL_UP and mb.pressed:
			zoom = min(ZOOM_MAX, zoom * 1.15)
			sprite.scale = Vector2(zoom, zoom)
		elif mb.button_index == MOUSE_BUTTON_WHEEL_DOWN and mb.pressed:
			zoom = max(ZOOM_MIN, zoom / 1.15)
			sprite.scale = Vector2(zoom, zoom)
		elif mb.button_index == MOUSE_BUTTON_LEFT and mb.pressed:
			if mb.position.x < get_viewport_rect().size.x - 410:
				_handle_world_click()
		elif mb.button_index == MOUSE_BUTTON_RIGHT:
			_dragging = mb.pressed
	elif event is InputEventMouseMotion and _dragging:
		var mm := event as InputEventMouseMotion
		cam.position -= mm.relative / zoom
	elif event is InputEventKey and event.pressed:
		var k := event as InputEventKey
		if k.keycode == KEY_SPACE:
			_toggle_play()
		elif k.keycode == KEY_R and not k.ctrl_pressed:
			_reset_world()
		elif k.keycode == KEY_EQUAL or k.keycode == KEY_PLUS:
			zoom = min(ZOOM_MAX, zoom * 1.15)
			sprite.scale = Vector2(zoom, zoom)
		elif k.keycode == KEY_MINUS:
			zoom = max(ZOOM_MIN, zoom / 1.15)
			sprite.scale = Vector2(zoom, zoom)

var _dragging := false

func _world_cell_at_mouse() -> Vector2i:
	var mouse := get_viewport().get_mouse_position()
	var c := get_viewport().get_canvas_transform().affine_inverse() * mouse
	var cell := c / zoom + Vector2(sim.W / 2.0, sim.H / 2.0)
	return Vector2i(int(cell.y), int(cell.x))

func _handle_world_click() -> void:
	var cell := _world_cell_at_mouse()
	if cell.x < 0 or cell.x >= sim.H or cell.y < 0 or cell.y >= sim.W:
		return
	last_cell = cell
	if place_mode == 1:
		sim.remove_at(cell)
		_status("已删除 (%d,%d) 分子" % [cell.x, cell.y])
	else:
		var f := formula_edit.text.strip_edges()
		if f == "":
			return
		var pid = sim.place(f, cell)
		if pid >= 0:
			_status("已放置 %s @ (%d,%d)" % [f, cell.x, cell.y])
		else:
			_status("放置失败：%s 找不到空位（k=%d）" % [f, sim.info(f).get("k", 1)])
		_refresh_image()

func _query_formula() -> void:
	var f := formula_edit.text.strip_edges()
	var d = sim.info(f)
	if d.is_empty():
		info_label.text = "查不到 %s" % f
		return
	var a: Dictionary = d.get("attrs", {})
	var hw: Dictionary = sim.p.get("heat_w", {})
	info_label.text = "%s：%d 原子，k=%d 骨架格，A=%.2f D=%.2f 吸引半径=%d 排斥半径=%d 热值=%d（权重 C=%.1f L=%.1f F=%.1f） 格子=%s（质量 %.2f / 物态 %.2f）" % [
		f, int(d.get("natoms", 0)), int(d.get("k", 1)), float(d.get("A", 0.0)),
		float(d.get("D", 0.0)), int(d.get("ratt", 1)), int(d.get("rrep", 1)),
		int(d.get("heat", 0)), float(hw.get("C", 0.0)), float(hw.get("L", 0.0)), float(hw.get("F", 0.0)),
		String(d.get("cell", "")),
		float(a.get("mass", 0.0)), float(a.get("state", 0.0))]

# ---------------- 投料 ----------------
func _toggle_play() -> void:
	running = not running
	_status("运行中…" if running else "已暂停")

func _feed_rows(elements: Array, n: int) -> Array:
	var r = client.call_sync("feed", {"elements": elements, "n": n})
	if not r.get("ok", false):
		_status("投料失败：%s" % String(r.get("error", "?")))
		return []
	return r["data"].get("rows", [])

func _apply_preset() -> void:
	var id := preset_opt.selected
	var n := int(feed_n_edit.value)
	if id <= 3:
		_apply_t91(id, n)
	elif id <= 9:
		var subsets := [
			["O", "F", "L"], ["O", "X", "C"], ["O", "X", "K", "F"],
			["O", "X", "K", "A", "F"], ["O", "X", "C", "K", "A", "F"],
			["O", "X", "C", "K", "A", "F", "P", "W", "L"],
		]
		_feed_elements_preset(subsets[id - 4], n)
	else:
		var els: Array = []
		for e in elem_checks.keys():
			if elem_checks[e].button_pressed:
				els.append(e)
		if els.is_empty():
			_status("请至少勾选一个元素")
			return
		_feed_elements_preset(els, n)

func _apply_t91(kind: int, n: int) -> void:
	var presets := [
		["XK2F4", "XKF", "KF3"],
		["XP2F4", "XPF", "PF3"],
		["O2AF4", "OAF", "OF3"],
		["O2WF4", "OWF", "OF3"],
	]
	var a: String = presets[kind][0]
	var b: String = presets[kind][1]
	var c: String = presets[kind][2]
	sim.setup(int(W_edit.value), int(H_edit.value), client)
	sim.reset()
	# 主体 A：中心小圆盘 19 个
	var cr = int(sim.H / 2)
	var cc = int(sim.W / 2)
	var cells: Array = [Vector2i(0, 0)]
	for dr in range(-2, 3):
		for dc in range(-2, 3):
			if dr * dr + dc * dc <= 4 and not (dr == 0 and dc == 0):
				cells.append(Vector2i(dr, dc))
	for off in cells:
		sim.place(a, Vector2i(cr + off.x, cc + off.y))
	# 食物 B/C 随机撒入
	var per = max(20, int(n / 2))
	for i in range(per):
		sim.place(b, Vector2i(sim.rng.randi_range(0, sim.H - 1), sim.rng.randi_range(0, sim.W - 1)))
	for i in range(per):
		sim.place(c, Vector2i(sim.rng.randi_range(0, sim.H - 1), sim.rng.randi_range(0, sim.W - 1)))
	_refresh_image()
	_status("T91 预设：主体 %s ×%d，食物 %s/%s 各 %d" % [a, cells.size(), b, c, per])

func _apply_checked(n: int) -> void:
	var els: Array = []
	for e in elem_checks.keys():
		if elem_checks[e].button_pressed:
			els.append(e)
	if els.is_empty():
		_status("请至少勾选一个元素")
		return
	_feed_elements_preset(els, n)

func _feed_elements_preset(els: Array, n: int) -> void:
	var rows := _feed_rows(els, n)
	if rows.is_empty():
		return
	_rebuild_world(int(W_edit.value), int(H_edit.value))
	sim.load_feed(rows)
	_refresh_image()
	_status("已投料 %d 分子：%s（%d 种）" % [n, "".join(els), rows.size()])
	_refresh_image()

# ---------------- 存档 ----------------
func _save_state() -> void:
	var d = sim.save_json()
	d["tick_done"] = tick_done
	var f := FileAccess.open("user://chemlab_state.json", FileAccess.WRITE)
	if f:
		f.store_string(JSON.stringify(d))
		_status("状态已保存到 user://chemlab_state.json")
	else:
		_status("保存失败")

func _load_state() -> void:
	var f := FileAccess.open("user://chemlab_state.json", FileAccess.READ)
	if not f:
		_status("没有可读取的存档")
		return
	var d = JSON.parse_string(f.get_as_text())
	if typeof(d) != TYPE_DICTIONARY:
		_status("存档解析失败")
		return
	_rebuild_world(int(d.get("W", 200)), int(d.get("H", 140)))
	sim.load_json(d)
	_refresh_image()
	_status("已读取存档（tick=%d）" % int(d.get("tick", 0)))

func _export_csv() -> void:
	var f := FileAccess.open("user://chemlab_stats.csv", FileAccess.WRITE)
	if not f:
		_status("CSV 打开失败")
		return
	f.store_line("tick,n,species,complete,incomplete,none,drops,joins,T_env,rho")
	var rows: Array = chart.series.get("n", [])
	for i in range(rows.size()):
		f.store_line("%d,%d,%d,%d,%d,%d,%d,%d,%.2f,%.4f" % [
			i * 3, int(rows[i]),
			int(chart.series["species"][i]) if i < chart.series["species"].size() else 0,
			int(chart.series["T_env"][i]) if i < chart.series["T_env"].size() else 0,
			0, 0, 0, 0,
			float(chart.series["T_env"][i]) if i < chart.series["T_env"].size() else 0.0,
			0.0])
	_status("已导出 user://chemlab_stats.csv")

func _screenshot() -> void:
	var img := get_viewport().get_texture().get_image()
	if img == null:
		_status("截图失败：当前渲染模式取不到画面")
		return
	img.save_png("user://chemlab_screenshot.png")
	_status("截图已保存 user://chemlab_screenshot.png")


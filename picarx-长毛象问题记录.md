# picarx-树莓派程序问题记录

rpicam-jpeg -n --width 800 --height 600 --rotation 180 -o test_img_xxx1.jpg

- [ ] 摄像头画面相比 rapicam-jpeg 画面亮度不足
- [ ] 图像模糊。貌似对焦不清晰

# picarx-长毛象问题记录

- [ ] 删除搜索信号
- [ ] 所有校准去掉确认键，取消键改为返回键
- [ ] websocket 连接测试客户端测试完成后没有关闭
- [ ] 可能需要增加电机方向校准和 舵机初始角度校准
- [ ] 点击舞台后，放置的块消失
- [ ] app 点击暂停，控制停止，但是传感器读值一直在更新
- [ ] picarx scratch gpt
  - [ ] 启动 gpt
  - [ ] listen_and_stt -> txt
  - [ ] chat -> txt
  - [ ] stt
- [ ] 摄像头校准取图要取完整，包含下面的舵机
- [ ] 灰度值， 图像识别等数据包含多个变量，需要做成下拉列表的块
- [x] 音效阻塞运行，需要返回完成？
- [x] 音效判断重复的问题，需要 app 点击发送后复位值
- [ ] 完善报错信息返回
- [x] 修改避障模式实体定义 0 关， 1 避障， (没有跟随)
- [x] 程序报错 terminate called without an active exception
- [x] 程序报错 [Errno 24] Too many open files
  - [x] get_battery_voltage 重复创建 ADC, 回收机制没有关闭 i2c 文件符
- [x] front_sound_effect 没有结束
- [x] 设置速度删掉
- [x] 前进，后退？
- [x] 记录已经连接过的IP，下次优先扫描
- [x] 摄像头校准方向按钮应该放在上下左右。
- [x] 摄像头校准的上下方向反了

# React App 问题记录

- [ ] 进入避障模式没有发送数据
- [ ] 摇杆没有发送数据
- [ ] 灰度，超声波 没有变化
- [ ] 电压没有值
- [ ] 画面被拉伸变形
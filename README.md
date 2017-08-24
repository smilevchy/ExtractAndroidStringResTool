# ExtractAndroidStringResTool.py
提取出 Android 项目中硬编码的中文字符串到资源文件中

如果某个文件或者目录不需要抽取，需要在 filterlist.txt 中添加相应的配置。配置规则在 filterlist.txt 中

## How to use
1. 进入脚本文件所在目录
2. 执行命令: python extractAndroidStringResTool.py [scanned_dir]

### 参数解释
scanned_dir : 待扫描的目录(一般是项目根目录)

## 后续特性开发:
1. 支持扫描单文件
2. 提高资源提取准确性
3. 支持识别扫描文件所属类性质(Activity/Fragment/Non-Context-Based-Class)
4. 提高资源 Id 替换成功率

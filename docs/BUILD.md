# 打包与安装指南

AkariBot Studio 有两种形态：**网页版（PWA，可"安装"到手机桌面）** 和 **安卓 App（APK）**。

---

## 一、网页版 / PWA（最快）

后端启动后，浏览器打开 `http://<服务器>:8099/`：

- **安卓 Chrome**：菜单 →「添加到主屏幕」/「安装应用」
- **iOS Safari**：分享 →「添加到主屏幕」
- **电脑 Chrome**：地址栏右侧出现「安装」图标

安装后图标、全屏、离线缓存都有（manifest + service worker 已内置）。

---

## 二、安卓 APK（Capacitor 打包）

### 依赖

| 组件 | 版本要求 |
|---|---|
| JDK | 21（Capacitor 7 要求） |
| Node.js | 18+ |
| Android SDK | cmdline-tools + platforms;android-34 + build-tools;34.0.0 |

### 安装 Android SDK

```bash
mkdir -p ~/Android/Sdk/cmdline-tools
curl -sL -o /tmp/cmdtools.zip https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip
unzip -q -o /tmp/cmdtools.zip -d ~/Android/Sdk/cmdline-tools
mv ~/Android/Sdk/cmdline-tools/cmdline-tools ~/Android/Sdk/cmdline-tools/latest

export ANDROID_HOME=$HOME/Android/Sdk
yes | $ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager --sdk_root=$ANDROID_HOME --licenses
$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager --sdk_root=$ANDROID_HOME \
  "platform-tools" "platforms;android-34" "build-tools;34.0.0"
```

### 生成 / 构建

```bash
cd ~/projects/akari-qqbot
npm install
npx cap add android      # 首次
npx cap sync android     # 每次改完前端后同步

export ANDROID_HOME=$HOME/Android/Sdk
cd android && ./gradlew assembleDebug
```

产物：`android/app/build/outputs/apk/debug/app-debug.apk`

### 装到手机

```bash
adb install -r android/app/build/outputs/apk/debug/app-debug.apk
```

或直接把 APK 传到手机点击安装（需允许「未知来源」）。

---

## 三、App 连接后端

APK 内置的是前端界面，数据要靠后端。首次打开 App：

1. 进「我的」页 → **服务器地址**
2. 填入后端地址，例如 `http://43.172.77.240:8099` 或 `https://bot.landisha.icu`
3. 「保存并重连」

> 后端必须能被手机访问到（同一局域网 / 公网 IP / 域名 + HTTPS）。
> 用 HTTPS 时 WebSocket 会自动走 `wss://`。

---

## 四、签名发布版（可选）

debug 包够自用。要发布/长期安装请生成正式签名：

```bash
keytool -genkey -v -keystore akaribot.keystore -alias akaribot \
  -keyalg RSA -keysize 2048 -validity 10000
cd android && ./gradlew assembleRelease
```

并把 keystore 路径填入 `android/app/build.gradle` 的 `signingConfigs`。

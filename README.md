# TVBox 配置

自用 TVBox / OK影视 配置，包含 288 个点播源和 2 条直播线路。

## 配置地址

GitHub Pages（推荐，走 CDN）：

```
https://huang-tao-hunter.github.io/tvbox-public/my.json
```

raw 备用：

```
https://raw.githubusercontent.com/huang-tao-hunter/tvbox-public/master/my.json
```

国内访问 raw 不稳定时，可在前面加代理前缀，例如
`https://github.moeyy.xyz/https://raw.githubusercontent.com/huang-tao-hunter/tvbox-public/master/my.json`。

## 使用

在 OK影视 / TVBox 的「配置地址」中填入上面的 Pages 地址，保存后回到首页等待加载即可。

## 目录说明

| 路径 | 内容 |
|---|---|
| `my.json` | 配置入口，客户端只读这一个文件 |
| `jar/` | spider jar（配置里带 md5 校验，换 jar 必须同步更新 md5） |
| `js/`、`lib/` | drpy 脚本源和运行时 |
| `json/` | 部分源依赖的分类/索引数据 |
| `tvlive.txt` | 直播源 |
| `tools/private.py` | 校验配置：重算 jar md5、剔除本地文件缺失的源 |

推送到 `master` 后，`.github/workflows/private.yml` 会自动跑一次校验，有变化才提交。

## 免责声明

- 本仓库仅包含配置索引与第三方脚本，不托管、不存储、不转码任何影视内容。
- 所有资源均来自网络公开接口，版权归原作者所有。
- 仅供个人学习研究使用，请于 24 小时内删除；禁止转载、分发或用于商业用途。
- 使用本仓库内容产生的一切后果由使用者自行承担。

如有侵权，请提交 Issue 或联系仓库所有者删除。

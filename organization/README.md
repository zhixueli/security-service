# 在 AWS Organization 中的多个账号多个 Region 下启用或者关闭 AWS GuardDuty 以及 AWS SecurityHub 服务

本项目旨在以自动化的流程在 AWS Organization 中的多个账号多个 Region 下启用或者关闭 AWS GuardDuty 以及 AWS SecurityHub 服务

## GuardDuty

在启用 AWS GuardDuty 服务过程中，在每一个需要启用的 Region 将会执行以下步骤：

* 启用 Organization 中的管理账号的 GuardDuty 服务

* 指定 GuardDuty 委托管理员，一般指定为 Organization 中的管理账号

* 将 Organization 下所有子账号的 GuardDuty 服务与管理账号关联并启用 GuardDuty 服务

* 启用 Organization 下新添加账号自动 Enable GuardDuty 服务

在关闭 AWS GuardDuty 服务过程中，在每一个需要启用的 Region 将会执行以下步骤：

* 将 Organization 下所有子账号的 GuardDuty 服务与管理账号解除关联并关闭 GuardDuty 服务

* 禁用 Organization 中的 GuardDuty 委托管理员

* 关闭 Organization 中的管理账号的 GuardDuty 服务 （可选，通过参数 --disable_master 设置）

### 准备工作

* 在 Organization 的管理账号上检查 GuardDuty 服务的各个 Region 中是否存在通过邀请形式添加 GuardDuty 服务的子账号（GuardDuty->Settings->Accounts），如果的话需要先删除关联

* 步骤中所有脚本需要在在 Organization 的管理账号上以管理员身份执行。

### 启用 GuardDuty 操作

```
python enableguarddutyfororg.py \
    --master_account 123456789012 \
    --enabled_regions us-east-1,us-west-2
```

* 命令参数 --master_account 参数指定AWS Organization 中的管理账号 ID
* 命令参数 --enabled_regions 指定子账号启用服务的区域，多个区域使用逗号隔开，如不指定将在所有可用区域开启

### 关闭 GuardDuty 操作

```
python disableguarddutyfororg.py \
    --master_account 123456789012 \
    --enabled_regions us-east-1,us-west-2 \
    --disable_master
```

* 命令参数 --master_account 参数指定AWS Organization 中的管理账号 ID
* 命令参数 --enabled_regions 指定关闭子账号服务的区域，多个区域使用逗号隔开，如不指定将在所有可用区域关闭
* 命令参数 --disable_master 指定是否需要在 Organization 中的管理账号关闭 GuardDuty 服务，默认情况下添加此参数不关闭管理账号的 GuardDuty 服务


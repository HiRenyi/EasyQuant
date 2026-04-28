# Factor Mining Knowledge Base

## Rules
| 文件 | 标签 | 摘要 |
|------|------|------|
| [ratio_signals_dominate](rules/ratio_signals_dominate.md) | ratio, structure | 比值信号 rank(A/B) 持续优于乘法 rank(A)*rank(B) 和加法 rank(A)+rank(B) |
| [hs300_first](rules/hs300_first.md) | universe | hs300 表现持续强�� csi500，优先在 hs300 验证 |
| [robustness_validation_required](rules/robustness_validation_required.md) | validation, robustness | 因子采用前必须通过子区间/跨市场/样本外三重验证 [Agent+DS 共识] |

## Findings
| 文件 | 标签 | 摘要 |
|------|------|------|
| [vwap_deviation_best_seed](findings/vwap_deviation_best_seed.md) | vwap, seed, near_A | VWAP Decay Alpha: WQ BRAIN 6/7 PASS (Sharpe=1.47, Fitness=0.73)，最强种子 |
| [reversal_5d_baseline](findings/reversal_5d_baseline.md) | reversal, baseline | 5日反转 rank(-ret5) 是稳定基线，Sharpe~1.17 |
| [adv20_volume_enhancer](findings/adv20_volume_enhancer.md) | volume, enhancer | adv20/volume 乘数增强所有因子族 30-80%，但时间稳定性存疑 |
| [low_vol_base_alpha](findings/low_vol_base_alpha.md) | volatility, baseline | 低波因子 -ts_mean((high-low)/close,5) 在 hs300 有稳定 alpha，fitness ~0.8-1.0 |

## Failures
| 文件 | 标签 | 摘要 |
|------|------|------|
| [multiplicative_weak](failures/multiplicative_weak.md) | multiplicative | rank(A)*rank(B) 乘法组合 Sharpe 一般 <0.8，不如比值 |
| [pure_volume_weak](failures/pure_volume_weak.md) | volume | 纯量信号（无价格成分）IC 接近零 |
| [temporal_instability_lowvol_volume](failures/temporal_instability_lowvol_volume.md) | overfitting, low-vol, dead-end | 低波因子族整体证伪：子区间/跨市场/样本外全线失效 [Agent+DS 共识] |
| [vwap_deviation_unstable](failures/vwap_deviation_unstable.md) | vwap, unstable, dead-end | VWAP偏离因子族整体证伪：44个表达式三重验证全部失败 [Agent+DS 共识] |

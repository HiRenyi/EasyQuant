# Factor Mining Knowledge Base

## Rules
| 文件 | 标签 | 摘要 |
|------|------|------|
| [ratio_signals_dominate](rules/ratio_signals_dominate.md) | ratio, structure | 比值信号 rank(A/B) 持续优于乘法 rank(A)*rank(B) 和加法 rank(A)+rank(B) |
| [hs300_first](rules/hs300_first.md) | universe | hs300 表现持续强于 csi500，优先在 hs300 验证 |

## Findings
| 文件 | 标签 | 摘要 |
|------|------|------|
| [vwap_deviation_best_seed](findings/vwap_deviation_best_seed.md) | vwap, seed | VWAP 偏离信号 fitness=0.955, Sharpe=1.659，最强种子 |
| [reversal_5d_baseline](findings/reversal_5d_baseline.md) | reversal, baseline | 5日反转 rank(-ret5) 是稳定基线，Sharpe~1.17 |
| [adv20_volume_enhancer](findings/adv20_volume_enhancer.md) | volume, enhancer | adv20/volume 乘数增强所有因子族 30-80%，但时间稳定性存疑 |
| [low_vol_base_alpha](findings/low_vol_base_alpha.md) | volatility, baseline | 低波因子 -ts_mean((high-low)/close,5) 在 hs300 有稳定 alpha，fitness ~0.8-1.0 |

## Failures
| 文件 | 标签 | 摘要 |
|------|------|------|
| [multiplicative_weak](failures/multiplicative_weak.md) | multiplicative | rank(A)*rank(B) 乘法组合 Sharpe 一般 <0.8，不如比值 |
| [pure_volume_weak](failures/pure_volume_weak.md) | volume | 纯量信号（无价格成分）IC 接近零 |
| [temporal_instability_lowvol_volume](failures/temporal_instability_lowvol_volume.md) | overfitting, temporal | 低波+缩量组合 近期A级但历史C级，时间稳定性差 |

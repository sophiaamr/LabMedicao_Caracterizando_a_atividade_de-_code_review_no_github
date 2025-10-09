import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.stats import spearmanr

df = pd.read_csv("dataset.csv")
df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")

col_desc = "descricao_len"
col_reviews = "num_review_comments"

df = df[(df[col_desc] > 0) & (df[col_reviews] >= 0)]

corr, p_value = spearmanr(df[col_desc], df[col_reviews])
print(f"Correlação de Spearman ({col_desc} vs {col_reviews}): ρ = {corr:.3f}, p = {p_value:.4f}")

plt.figure(figsize=(9,6))
sns.regplot(
    data=df,
    x=col_desc,
    y=col_reviews,
    scatter_kws={"alpha":0.4, "s":40},
    line_kws={"color":"red"}
)
plt.title(
    "RQ07 - Relação entre a descrição dos PRs e o número de revisões\n"
    f"(p = {corr:.3f}, p < 0.0001)",
    fontsize=13
)
plt.xlabel("Tamanho da descrição do PR (nº de caracteres)")
plt.ylabel("Número de comentários de revisão (revisões realizadas)")
plt.grid(alpha=0.3)
plt.tight_layout()
plt.show()

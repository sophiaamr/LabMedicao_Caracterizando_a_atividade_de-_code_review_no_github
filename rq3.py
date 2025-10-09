import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.stats import spearmanr

df = pd.read_csv("dataset.csv")
df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")

col_desc = "descricao_len"
col_feedback = "num_review_comments"

df = df[(df[col_desc] > 0) & (df[col_feedback] >= 0)]

corr, p_value = spearmanr(df[col_desc], df[col_feedback])
print(f"Correlação de Spearman ({col_desc} vs {col_feedback}): ρ = {corr:.3f}, p < {p_value:.4f}")

plt.figure(figsize=(9,6))
sns.regplot(
    data=df,
    x=col_desc,
    y=col_feedback,
    scatter_kws={"alpha":0.4, "s":40},
    line_kws={"color":"red"},
    lowess=True
)
plt.title(
    "RQ03: Relação entre a descrição dos PRs e o feedback final das revisões\n"
    f"(o = {corr:.3f}, p < 0.0001)",
    fontsize=13
)
plt.xlabel("Tamanho da descrição do PR (nº de caracteres)")
plt.ylabel("Número de comentários de revisão")
plt.grid(alpha=0.3)
plt.tight_layout()
plt.show()

df["faixa_desc"] = pd.cut(
    df[col_desc],
    bins=[0, 200, 500, 1000, 2000, 5000, df[col_desc].max()],
    labels=["≤200", "201-500", "501-1000", "1001-2000", "2001-5000", ">5000"]
)

plt.figure(figsize=(8,5))
sns.boxplot(data=df, x="faixa_desc", y=col_feedback, palette="Blues")
plt.title("Distribuição de feedbacks (comentários) por faixa de tamanho da descrição")
plt.xlabel("Faixa de caracteres da descrição")
plt.ylabel("Nº de comentários de revisão")
plt.grid(alpha=0.3)
plt.tight_layout()
plt.show()

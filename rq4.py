import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.stats import spearmanr

df = pd.read_csv("dataset.csv")
df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")

col_feedback = "num_review_comments"
col_inter1 = "num_participants"
col_inter2 = "num_comentarios"

df = df[(df[col_feedback] >= 0) & (df[col_inter1] >= 0) & (df[col_inter2] >= 0)]

corr_part, p_part = spearmanr(df[col_inter1], df[col_feedback])
corr_coment, p_coment = spearmanr(df[col_inter2], df[col_feedback])

print("Correlação de Spearman (participantes vs feedback):")
print(f"p = {corr_part:.3f}, p < {p_part:.4f}")
print("\nCorrelação de Spearman (comentários vs feedback):")
print(f"p = {corr_coment:.3f}, p < {p_coment:.4f}")

plt.figure(figsize=(8,6))
sns.regplot(
    data=df,
    x=col_inter1,
    y=col_feedback,
    scatter_kws={"alpha":0.4, "s":40},
    line_kws={"color":"red"}
)
plt.title(
    f"RQ04 - Relação entre nº de participantes e feedback das revisões\n"
    f"(p = {corr_part:.3f}, p < 0.0001)",
    fontsize=13
)
plt.xlabel("Número de participantes no PR")
plt.ylabel("Número de comentários de revisão")
plt.grid(alpha=0.3)
plt.tight_layout()
plt.show()

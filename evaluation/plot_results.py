import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

def main():
    # Paths
    base_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(base_dir, "..", "results", "evaluation_summary.csv")
    output_path = os.path.join(base_dir, "..", "results", "evaluation_metrics_chart.png")
    
    if not os.path.exists(csv_path):
        print(f"Error: CSV file not found at {csv_path}")
        return
        
    # Read data
    df = pd.read_csv(csv_path)
    print("Loaded evaluation metrics:")
    print(df)
    
    # Set styling
    sns.set_theme(style="whitegrid")
    plt.rcParams.update({
        'font.family': 'sans-serif',
        'font.size': 11,
        'axes.labelsize': 12,
        'axes.titlesize': 14,
        'xtick.labelsize': 10,
        'ytick.labelsize': 10,
        'figure.titlesize': 16
    })
    
    # Melt dataframe for plotting multiple metrics per dataset
    metrics = ['Precision', 'Recall', 'F1_Score']
    df_melted = pd.melt(
        df, 
        id_vars=['Dataset'], 
        value_vars=metrics, 
        var_name='Metric', 
        value_name='Score'
    )
    
    # Create figure
    plt.figure(figsize=(10, 6))
    
    # Custom color palette (modern medical-themed)
    palette = {
        'Precision': '#3F72AF',  # Muted Blue
        'Recall': '#957DAD',     # Lavender
        'F1_Score': '#FF7597'    # Coral Pink
    }
    
    ax = sns.barplot(
        data=df_melted, 
        x='Dataset', 
        y='Score', 
        hue='Metric', 
        palette=palette,
        edgecolor='black',
        linewidth=0.5
    )
    
    # Add values on top of bars
    for p in ax.patches:
        height = p.get_height()
        if height > 0.0:
            ax.annotate(
                f'{height:.2f}',
                (p.get_x() + p.get_width() / 2., height),
                ha='center', 
                va='center', 
                xytext=(0, 8), 
                textcoords='offset points',
                fontsize=9,
                fontweight='semibold'
            )
            
    # Labels & Title
    plt.title("MedFactCheck Pipeline Performance across Datasets", pad=20, fontweight='bold', color='#222831')
    plt.xlabel("Evaluation Dataset", labelpad=10, fontweight='semibold')
    plt.ylabel("Score (0.0 - 1.0)", labelpad=10, fontweight='semibold')
    plt.ylim(0, 1.15) # Leave room for value labels
    
    plt.legend(title="Metrics", bbox_to_anchor=(1.02, 1), loc='upper left', frameon=True)
    plt.tight_layout()
    
    # Save plot
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Successfully generated and saved chart to:\n-> {output_path}")

if __name__ == "__main__":
    main()

import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

def main():
    # Paths
    base_dir = os.path.dirname(os.path.abspath(__file__))
    # The summary is generated as final_evaluation_summary.csv inside evaluation/results/pipeline_predictions/
    csv_path = os.path.join(base_dir, "results", "pipeline_predictions", "final_evaluation_summary.csv")
    output_path = os.path.join(base_dir, "results", "evaluation_metrics_chart.png")
    
    if not os.path.exists(csv_path):
        print(f"Error: CSV file not found at {csv_path}")
        return
        
    # Read data
    df = pd.read_csv(csv_path)
    print("Loaded evaluation metrics:")
    print(df)
    
    # Format Dataset names to Title Case for cleaner academic presentation
    dataset_mapping = {
        'SCIFACT': 'SciFact',
        'BIOASQ': 'BioASQ',
        'HEALTHFC': 'HealthFC'
    }
    df['Dataset'] = df['Dataset'].map(lambda x: dataset_mapping.get(x.upper(), x))
    
    # Set academic/paper styling (Serif fonts, clean layout)
    sns.set_theme(style="white")
    plt.rcParams.update({
        'font.family': 'serif',
        'font.serif': ['Times New Roman', 'DejaVu Serif', 'Liberation Serif', 'serif'],
        'font.size': 10.5,
        'font.weight': 'semibold',           # Make default font weight semibold (slightly bolder/thicker)
        'axes.labelweight': 'semibold',      # Make axes labels semibold
        'axes.titleweight': 'bold',          # Make title bold
        'axes.labelsize': 11.5,
        'axes.titlesize': 12,
        'xtick.labelsize': 10,
        'ytick.labelsize': 10,
        'legend.fontsize': 9.5,
        'figure.titlesize': 13,
        'text.usetex': False
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
    
    # Create compact figure matching single/double-column paper width ratios
    fig, ax = plt.subplots(figsize=(6.5, 4.2))
    
    # Academic/Paper palette (high-contrast professional colors, printable in grayscale)
    palette = {
        'Precision': '#1f4e79',  # Dark Steel Blue
        'Recall': '#8c2d19',     # Muted Crimson
        'F1_Score': '#595959'    # Slate Gray
    }
    
    # Draw bars
    sns.barplot(
        data=df_melted, 
        x='Dataset', 
        y='Score', 
        hue='Metric', 
        palette=palette,
        edgecolor='black',
        linewidth=0.8,
        ax=ax
    )
    
    # Apply hatching patterns to ensure readability in black & white printing
    hatches = ['//', '\\\\', '..']  # Diagonal, Back-diagonal, Stipple/Dots
    for i, container in enumerate(ax.containers):
        # The index i corresponds directly to the metric/hue index
        for patch in container:
            patch.set_hatch(hatches[i])
        
    # Annotate score values on top of the bars
    for p in ax.patches:
        height = p.get_height()
        if height > 0.0:
            ax.annotate(
                f'{height:.2f}',
                (p.get_x() + p.get_width() / 2., height),
                ha='center', 
                va='center', 
                xytext=(0, 6), 
                textcoords='offset points',
                fontsize=8.5,
                fontweight='semibold'
            )
            
    # Academic Spines & Grid
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(True)
    ax.spines['bottom'].set_visible(True)
    
    # Make spines look crisp
    for spine in ['left', 'bottom']:
        ax.spines[spine].set_color('black')
        ax.spines[spine].set_linewidth(0.8)
        
    # Add thin, light horizontal gridlines for reference, behind the bars
    ax.yaxis.grid(True, linestyle='--', alpha=0.5, color='#cccccc')
    ax.set_axisbelow(True)
    
    # Ticks pointing outwards
    ax.tick_params(direction='out', length=4, width=0.8, colors='black')
    
    # Labels & Title (Simple, clean title for academic look)
    plt.title("Benchmark Metrics", pad=15, fontweight='bold', color='black')
    plt.xlabel("Evaluation Dataset", labelpad=8)
    plt.ylabel("Metric Score", labelpad=8)
    plt.ylim(0, 1.15)  # Buffer for the annotations
    
    # Format the legend with matching hatches and a clean black border
    legend = ax.legend(title="Metrics", loc='upper right', frameon=True, framealpha=1.0, facecolor='white', edgecolor='black')
    legend.get_frame().set_linewidth(0.8)
    
    # Update legend handles with the matching hatches
    # Check if legend_handles is available (matplotlib >= 3.6), else fallback to legendHandles
    handles = getattr(legend, 'legend_handles', getattr(legend, 'legendHandles', None))
    if handles:
        for i, handle in enumerate(handles):
            handle.set_hatch(hatches[i])
            handle.set_edgecolor('black')
            handle.set_linewidth(0.8)
            
    plt.tight_layout()
    
    # Save high-resolution figure (DPI 300 is standard for print publications)
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    
    print(f"Successfully generated and saved academic chart to:\n-> {output_path}")

if __name__ == "__main__":
    main()

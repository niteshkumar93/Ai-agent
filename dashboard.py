import streamlit as st
import plotly.express as px
import pandas as pd


def render_dashboard(df):

    st.markdown("## 📊 Dashboard — Test Failure Insights")

    # ---------------------------------------------------------
    # 1️⃣ Failures Per XML File
    # ---------------------------------------------------------
    st.subheader("📁 Failures Per XML File")

    file_counts = (
        df.groupby("source")
        .size()
        .reset_index(name="failures")
    )

    fig1 = px.bar(
        file_counts,
        x="source",
        y="failures",
        title="Failures Per Uploaded XML File",
        text="failures",
        color="failures",
        color_continuous_scale="Blues"
    )
    fig1.update_layout(showlegend=False)
    st.plotly_chart(fig1, use_container_width=True)

    # ---------------------------------------------------------
    # 2️⃣ Failure Count Per Testcase
    # ---------------------------------------------------------
    st.subheader("🧪 Most Failing Testcases")

    testcase_counts = (
        df.groupby("testcase")
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )

    fig2 = px.bar(
        testcase_counts,
        x="testcase",
        y="count",
        title="Failures Per Testcase",
        text="count",
        color="count",
        color_continuous_scale="Reds"
    )
    fig2.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig2, use_container_width=True)

    # ---------------------------------------------------------
    # 3️⃣ Error Type Distribution (Pie Chart)
    # ---------------------------------------------------------
    st.subheader("❗ Error Type Distribution")

    # Clean short error labels for pie representation
    df["error_short"] = df["error"].str.slice(0, 40)

    fig3 = px.pie(
        df,
        names="error_short",
        title="Error Types Breakdown",
        hole=0.35,
        color_discrete_sequence=px.colors.qualitative.Safe
    )
    st.plotly_chart(fig3, use_container_width=True)

    # ---------------------------------------------------------
    # 4️⃣ (Optional) AI Summary Keyword Cloud
    #     Enabled only when AI is ON and analysis exists
    # ---------------------------------------------------------
    if "analysis" in df.columns and df["analysis"].str.len().sum() > 0:

        st.subheader("☁ Keyword Cloud From AI Summaries")

        # Build simple frequency map
        text = " ".join(df["analysis"].astype(str).tolist()).lower()
        keywords = pd.Series(text.split()).value_counts().head(20)

        fig4 = px.bar(
            keywords,
            x=keywords.index,
            y=keywords.values,
            title="Most Common AI Summary Keywords",
            text=keywords.values,
            color=keywords.values,
            color_continuous_scale="Tealgrn"
        )

        fig4.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig4, use_container_width=True)

    st.success("📊 Dashboard Loaded Successfully!")

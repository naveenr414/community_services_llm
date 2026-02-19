from ..app.rag_utils import get_all_embeddings

model, saved_indices, documents = get_all_embeddings({
    'cspnj': 'data/cspnj.csv',
    'clhs': 'data/clhs.csv'
})
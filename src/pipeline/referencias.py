"""Tabelas de referência usadas pela validação (V7, V9) e pela transformação (T5).

Os valores vieram do profiling da N2. Se o dataset ganhar uma cidade ou subcategoria nova,
a validação avisa em vez de aceitar em silêncio.
"""

CATEGORIAS = ("Clothing", "Electronics", "Furniture")

# V7: hierarquia categoria → subcategorias (17 no total, nenhuma em duas categorias)
SUBCATEGORIAS = {
    "Clothing": {"Saree", "Trousers", "Stole", "Hankerchief", "Shirt", "T-shirt", "Kurti", "Leggings", "Skirt"},
    "Electronics": {"Printers", "Phones", "Electronic Games", "Accessories"},
    "Furniture": {"Bookcases", "Chairs", "Tables", "Furnishings"},
}

# V9: pares cidade × estado válidos. Chandigarh é capital de Punjab e de Haryana, por isso aparece duas vezes.
CIDADE_ESTADO = {
    ("Ahmedabad", "Gujarat"), ("Allahabad", "Uttar Pradesh"), ("Amritsar", "Punjab"),
    ("Bangalore", "Karnataka"), ("Bhopal", "Madhya Pradesh"), ("Chandigarh", "Haryana"),
    ("Chandigarh", "Punjab"), ("Chennai", "Tamil Nadu"), ("Delhi", "Delhi"), ("Goa", "Goa"),
    ("Gangtok", "Sikkim"), ("Hyderabad", "Andhra Pradesh"), ("Indore", "Madhya Pradesh"),
    ("Jaipur", "Rajasthan"), ("Kashmir", "Jammu and Kashmir"), ("Kohima", "Nagaland"),
    ("Kolkata", "West Bengal"), ("Lucknow", "Uttar Pradesh"), ("Mumbai", "Maharashtra"),
    ("Patna", "Bihar"), ("Pune", "Maharashtra"), ("Simla", "Himachal Pradesh"), ("Surat", "Gujarat"),
    ("Thiruvananthapuram", "Kerala"), ("Udaipur", "Rajasthan"),
}

# T5: correções conhecidas (par errado → par certo). Delhi não fica em Madhya Pradesh.
CORRECOES_CIDADE_ESTADO = {
    ("Delhi", "Madhya Pradesh"): ("Delhi", "Delhi"),
}

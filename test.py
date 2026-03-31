import pandas as pd

# Crear los datos para la Hoja 1 (Con títulos arriba)
data1 = {
    'N° ANIMAL': [1020, 1307, 2306, 4589, 9999],
    'RAZA': ['BRAHMAN', 'GYROLH', 'BRAHMAN', 'NELORE', 'PRUEBA'],
    'PESO': [450, 380, 410, 425, 0]
}
df1 = pd.DataFrame(data1)

# Crear los datos para la Hoja 2 (Con nombres de columnas distintos)
data2 = {
    'REGISTRO': [7744, 8855, 1122],
    'SEXO': ['M', 'F', 'M'],
    'OBSERVACIONES': ['REVISIÓN PENDIENTE', 'SANA', 'SELECCIONADO']
}
df2 = pd.DataFrame(data2)

# Guardar en un Excel con formato "sucio"
with pd.ExcelWriter('test.xlsx', engine='openpyxl') as writer:
    # Escribir Hoja 1 empezando en la fila 4 (dejando espacio para basura arriba)
    df1.to_excel(writer, sheet_name='Potrero_Boral', startrow=4, index=False)
    
    # Escribir Hoja 2 empezando en la fila 6
    df2.to_excel(writer, sheet_name='Potrero_La_Linda', startrow=6, index=False)
    
    # Acceder a las hojas para poner los títulos decorativos que el bot debe ignorar
    workbook = writer.book
    
    sheet1 = workbook['Potrero_Boral']
    sheet1['A1'] = "INVENTARIO HACIENDA EL BORAL - MARZO 2026"
    sheet1['A2'] = "Versión: 002-RPA"
    
    sheet2 = workbook['Potrero_La_Linda']
    sheet2['A1'] = "REPORTE AUXILIAR"
    sheet2['A2'] = "NO PROCESAR ESTA CABECERA"

print("✅ Archivo 'PRUEBA_ARGOS.xlsx' creado con éxito. ¡Listo para la reunión!")
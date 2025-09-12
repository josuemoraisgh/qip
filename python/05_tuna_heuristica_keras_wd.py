import numpy as np
import pandas as pd
import tensorflow as tf
import keras
from keras import layers
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

# ================= CONFIGURAÇÃO =================
INPUT_PATH  = r"c:/SourceCode/qip/python/banco_dados.xlsx"
OUTPUT_PATH = r"c:/SourceCode/qip/python/banco_dados.xlsx"

EPOCHS      = 60
BATCH_SIZE  = 128
SEED        = 42
LR          = 0.001
ALPHA_INIT  = 1.0
DROPOUT     = 0.2
# ================================================

np.random.seed(SEED)
tf.random.set_seed(SEED)


def load_data(path):
    print(f"[INFO] Carregando dados de {path} ...")
    df = pd.read_excel(path, sheet_name="TDados_clean")
    y = df["Alvo"].astype(str).fillna("DESCONHECIDO")

    # Trata "não/nao" e vazio como DESCONHECIDO
    y = y.str.lower().replace({"não": "DESCONHECIDO", "nao": "DESCONHECIDO", "nan": "DESCONHECIDO"})
    mask_known = y != "DESCONHECIDO"

    X = df.drop(columns=["Alvo"]).values
    y_known = y[mask_known].values
    X_known = X[mask_known]
    X_unknown = X[~mask_known]

    print(f"[INFO] Total={len(df)}, Conhecidos={len(X_known)}, Desconhecidos={len(X_unknown)}")

    return X_known, y_known, X_unknown, df.index


def build_model(input_dim, num_classes):
    model = keras.Sequential([
        layers.Input(shape=(input_dim,)),
        layers.Dense(256, activation="relu",
                     kernel_initializer=keras.initializers.RandomNormal(mean=0.0, stddev=0.05)),
        layers.Dropout(DROPOUT),
        layers.Dense(128, activation="relu"),
        layers.Dropout(DROPOUT),
        layers.Dense(num_classes, activation="softmax")
    ])

    opt = keras.optimizers.Adam(learning_rate=LR)
    model.compile(optimizer=opt,
                  loss="sparse_categorical_crossentropy",
                  metrics=["accuracy"])
    return model


def run_pipeline(input_path, output_path, epochs, batch_size):
    X, y, X_unknown, idx_all = load_data(input_path)

    # Codifica rótulos
    le = LabelEncoder()
    y_enc = le.fit_transform(y)
    classes = le.classes_
    print(f"[INFO] Classes: {list(classes)}")

    # Split treino/val
    X_train, X_val, y_train, y_val = train_test_split(
        X, y_enc, test_size=0.33, random_state=SEED, stratify=y_enc
    )

    # Modelo
    model = build_model(X.shape[1], len(classes))

    # Treino
    history = model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=epochs,
        batch_size=batch_size,
        verbose=2
    )

    # Predição dos desconhecidos
    if len(X_unknown) > 0:
        preds_unknown = model.predict(X_unknown)
        top3_idx = np.argsort(-preds_unknown, axis=1)[:, :3]
        top3_labels = le.inverse_transform(top3_idx.flatten()).reshape(top3_idx.shape)
        print(f"[INFO] Predições para {len(X_unknown)} desconhecidos geradas.")
    else:
        preds_unknown, top3_labels = None, None

    # Salva resultados no Excel
    with pd.ExcelWriter(output_path, mode="a", if_sheet_exists="replace") as writer:
        # Histórico de treino
        pd.DataFrame(history.history).to_excel(writer, sheet_name="Metricas_Keras")

        # Predições desconhecidos
        if preds_unknown is not None:
            df_pred = pd.DataFrame({
                "Top1": top3_labels[:, 0],
                "Top2": top3_labels[:, 1],
                "Top3": top3_labels[:, 2]
            })
            df_pred.to_excel(writer, sheet_name="Predicoes_Desconhecidos", index=False)

    print(f"[FIM] Resultados salvos em {output_path}")


if __name__ == "__main__":
    print("[INFO] Configuração atual:")
    print(f"  INPUT={INPUT_PATH}")
    print(f"  OUTPUT={OUTPUT_PATH}")
    print(f"  EPOCHS={EPOCHS}, BATCH_SIZE={BATCH_SIZE}, LR={LR}, DROPOUT={DROPOUT}")

    run_pipeline(
        input_path=INPUT_PATH,
        output_path=OUTPUT_PATH,
        epochs=EPOCHS,
        batch_size=BATCH_SIZE,
    )
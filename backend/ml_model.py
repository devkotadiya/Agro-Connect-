"""Simple crop recommendation model using scikit-learn (open source)."""
from sklearn.tree import DecisionTreeClassifier

# Features: [nitrogen, phosphorus, potassium, temperature, humidity, rainfall]
X = [
    [90, 42, 43, 21, 82, 202],   # rice
    [20, 60, 20, 22, 65, 90],    # maize
    [40, 55, 40, 18, 55, 60],    # wheat
    [100, 30, 50, 27, 60, 80],   # cotton
]
y = ["rice", "maize", "wheat", "cotton"]

model = DecisionTreeClassifier(random_state=42)
model.fit(X, y)


def recommend_crop(n, p, k, temperature, humidity, rainfall):
    """Return the recommended crop name for the given soil and weather values."""
    return model.predict([[n, p, k, temperature, humidity, rainfall]])[0]


if __name__ == "__main__":
    print(recommend_crop(90, 42, 43, 21, 82, 202))
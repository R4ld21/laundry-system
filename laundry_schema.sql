-- laundry_schema.sql (MySQL version)
DROP DATABASE IF EXISTS LaundryDB;
CREATE DATABASE LaundryDB;
USE LaundryDB;

CREATE TABLE Customers (
    CustomerId INT AUTO_INCREMENT PRIMARY KEY,
    Name       VARCHAR(80)  NOT NULL,
    Phone      VARCHAR(20)  NULL,
    Email      VARCHAR(254) NULL,
    CreatedAt  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX IX_Customers_Email (Email)
);

CREATE TABLE Orders (
    OrderId     INT AUTO_INCREMENT PRIMARY KEY,
    CustomerId  INT NOT NULL,
    WeightKg    DECIMAL(6,2)  NOT NULL,
    RatePerKg   DECIMAL(8,2)  NOT NULL,
    TotalPrice  DECIMAL(10,2) NOT NULL,
    Status      VARCHAR(20)   NOT NULL,
    ReceivedAt  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CompletedAt DATETIME      NULL,
    CONSTRAINT FK_Orders_Customers FOREIGN KEY (CustomerId)
        REFERENCES Customers (CustomerId),
    CONSTRAINT CK_Orders_Weight CHECK (WeightKg > 0 AND WeightKg <= 50),
    CONSTRAINT CK_Orders_Rate   CHECK (RatePerKg > 0),
    CONSTRAINT CK_Orders_Total  CHECK (TotalPrice >= 0),
    CONSTRAINT CK_Orders_Status CHECK (Status IN ('Pending','Completed')),
    INDEX IX_Orders_Status (Status),
    INDEX IX_Orders_Customer (CustomerId)
);

-- Login users table
CREATE TABLE Users (
    UserId       INT AUTO_INCREMENT PRIMARY KEY,
    Username     VARCHAR(50)  NOT NULL UNIQUE,
    PasswordHash VARCHAR(255) NOT NULL,
    CreatedAt    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Sample users (password is 'admin123' for both, hashed with SHA2)
INSERT INTO Users (Username, PasswordHash) VALUES
('admin', SHA2('admin123', 256)),
('staff', SHA2('staff123', 256));

-- Sample customers
INSERT INTO Customers (Name, Email) VALUES
('Juan Dela Cruz', 'juandc@gmail.com'),
('Maria Santos',   'mariasantos@gmail.com');

-- Sample orders
INSERT INTO Orders (CustomerId, WeightKg, RatePerKg, TotalPrice, Status) VALUES
(1, 3.50, 50.00, 175.00, 'Pending'),
(2, 2.00, 50.00, 100.00, 'Completed');
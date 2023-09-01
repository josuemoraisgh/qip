import 'dart:core';
import 'package:flutter/material.dart';

class CustomButton extends StatelessWidget {
  final String title;
  final String value;
  final String groupValue;
  final Function(String?) onChanged;

  const CustomButton({
    super.key,
    required this.title,
    required this.value,
    required this.groupValue,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.all(5),
        child: ElevatedButton(
          style: ButtonStyle(
            backgroundColor: value == groupValue
                ? MaterialStateProperty.all<Color>(Colors.black54)
                : MaterialStateProperty.all<Color>(Colors.white),
            elevation: MaterialStateProperty.all(8),
            shape: MaterialStateProperty.all<RoundedRectangleBorder>(
              RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(18.0),
                side: const BorderSide(width: 0.2, color: Colors.black54),
              ),
            ),
          ),
          child: Text(
            title,
            style: TextStyle(
              fontSize: 18,
              color: value == groupValue ? Colors.white : Colors.black87,
            ),
          ),
          onPressed: () {
            onChanged(value);
          },
        ),
      );
}
